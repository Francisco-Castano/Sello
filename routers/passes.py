"""
Enrutador de FastAPI para la gestión de pases.
Maneja los endpoints para emitir tarjetas, sumar sellos a clientes y consultar el estado de fidelización.
"""

import re
import unicodedata
import uuid
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models
from GoogleWallet import MI_ISSUER_ID, generate_google_wallet_url, update_google_wallet_pass
from branding import card_design
from names import format_person_name
from program import ProgramError, points_for_amount, rewards_for_balance
from auth import get_current_business

router = APIRouter(
    prefix="/passes",
    tags=["Pases & Fidelidad"]
)

# Versión de la política de privacidad que acepta el cliente al registrarse.
# Cambiarla cuando se publique la versión revisada por un abogado.
PRIVACY_VERSION = "borrador-2026-10"

class UserRegisterRequest(BaseModel):
    name: str
    phone: str
    business_slug: str
    birthday_day: int | None = None
    birthday_month: int | None = None
    birthday_year: int | None = None
    accept_privacy: bool = False
    marketing_opt_in: bool = False

class AddPointsRequest(BaseModel):
    points: int | None = None      # Puntos a mano (también negativos, para corregir)
    amount: float | None = None    # Monto de la compra, si el comercio suma puntos según el monto
    description: str | None = None

class RedeemRequest(BaseModel):
    reward_id: str

def normalize_phone(phone: str) -> str | None:
    """Deja solo los dígitos. Acepta de 8 a 15 (con o sin código de país)."""
    digits = re.sub(r"\D", "", phone or "")
    return digits if 8 <= len(digits) <= 15 else None

MIN_BIRTH_YEAR = 1900

def parse_birth_date(day: int | None, month: int | None, year: int | None) -> date | None:
    """Fecha de nacimiento opcional: o vienen día, mes y año, o no viene ninguno."""
    if day is None and month is None and year is None:
        return None
    if day is None or month is None or year is None:
        raise HTTPException(status_code=400, detail="Completá el día, el mes y el año de tu nacimiento")
    try:
        birth_date = date(year, month, day)
    except ValueError:
        raise HTTPException(status_code=400, detail="La fecha de nacimiento no es válida")
    if not MIN_BIRTH_YEAR <= year or birth_date > date.today():
        raise HTTPException(status_code=400, detail="La fecha de nacimiento no es válida")
    return birth_date

def age_on(birth_year: int, birthday: str, today: date) -> int:
    """Edad cumplida a la fecha (birthday es "MM-DD")."""
    return today.year - birth_year - (today.strftime("%m-%d") < birthday)

def comparable_name(name: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())

@router.post("/crear-google")
def create_pass(data: UserRegisterRequest, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.slug == data.business_slug).first()
    if not business:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    if business.status != "active":
        raise HTTPException(status_code=403, detail="Este comercio todavía no está habilitado")

    name = format_person_name(data.name)
    if not name:
        raise HTTPException(status_code=400, detail="Ingresá tu nombre")
    phone = normalize_phone(data.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Ingresá un teléfono válido, con código de área")
    if not data.accept_privacy:
        raise HTTPException(status_code=400, detail="Para obtener tu tarjeta tenés que aceptar la política de privacidad")
    birth_date = parse_birth_date(data.birthday_day, data.birthday_month, data.birthday_year)

    # El teléfono identifica al cliente en todos los comercios
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if user and comparable_name(user.name) != comparable_name(name):
        # Evita que alguien que solo conoce un teléfono se lleve la tarjeta (y los puntos) de otra persona
        raise HTTPException(
            status_code=409,
            detail="Este teléfono ya está registrado con otro nombre. Si es tuyo, pedile ayuda al comercio."
        )
    if not user:
        user = models.User(name=name, phone=phone)
        db.add(user)
        db.flush()
    # La fecha de nacimiento se completa una vez; si el cliente ya la tenía no se pisa
    if birth_date and not user.birth_year:
        user.birthday = birth_date.strftime("%m-%d")
        user.birth_year = birth_date.year

    # Si ya tiene tarjeta en este comercio se le devuelve la misma, así los puntos no quedan repartidos
    existing_pass = db.query(models.Pass).filter(
        models.Pass.user_id == user.id,
        models.Pass.business_id == business.id
    ).order_by(models.Pass.created_at).first()

    # 16 caracteres hex para que los IDs no se puedan adivinar
    pass_id = existing_pass.id if existing_pass else f"sello_{uuid.uuid4().hex[:16]}"
    balance = existing_pass.balance if existing_pass else 0

    # Se firma el link antes de guardar, así un error de credenciales no deja datos a medias
    try:
        wallet_url = generate_google_wallet_url(
            issuer_id=MI_ISSUER_ID,
            pass_id=pass_id,
            user_name=user.name,
            design=card_design(business),
            balance=balance
        )
    except Exception as e:
        db.rollback()
        print(f"[GoogleWallet] No se pudo firmar el pase: {e!r}")
        raise HTTPException(
            status_code=503,
            detail="El servidor no tiene bien configuradas las credenciales de Google Wallet"
        )

    pass_obj = existing_pass or models.Pass(
        id=pass_id,
        business_id=business.id,
        user_id=user.id,
        balance=0,
        pass_type="loyalty"
    )
    pass_obj.privacy_accepted_at = datetime.utcnow()
    pass_obj.privacy_version = PRIVACY_VERSION
    pass_obj.marketing_opt_in = data.marketing_opt_in
    if not existing_pass:
        db.add(pass_obj)
    db.commit()
    db.refresh(pass_obj)

    return {
        "status": "ok",
        "existing": existing_pass is not None,
        "business": business.name,
        "client_name": format_person_name(user.name),
        "pass_id": pass_obj.id,
        "balance": pass_obj.balance,
        "wallet_url": wallet_url
    }

def get_business_pass(pass_id: str, business: models.Business, db: Session) -> models.Pass:
    """Busca el pase solo dentro del comercio logueado; los pases de otros comercios dan 404."""
    pass_obj = db.query(models.Pass).filter(
        models.Pass.id == pass_id,
        models.Pass.business_id == business.id
    ).first()
    if not pass_obj:
        raise HTTPException(status_code=404, detail="Pase no encontrado")
    return pass_obj

def pass_summary(pass_obj: models.Pass, business: models.Business) -> dict:
    """Lo que la caja necesita mostrar de un pase: cliente, saldo, cumpleaños, programa y premios."""
    birthday = pass_obj.user.birthday
    birth_year = pass_obj.user.birth_year
    today = date.today()
    return {
        "pass_id": pass_obj.id,
        "client_name": format_person_name(pass_obj.user.name),
        "birthday": birthday,
        "birthday_today": birthday == today.strftime("%m-%d"),
        "age": age_on(birth_year, birthday, today) if birthday and birth_year else None,
        "business": business.name,
        "balance": pass_obj.balance,
        "status": pass_obj.status,
        "program": {
            "points_mode": business.points_mode,
            "points_per_visit": business.points_per_visit,
            "pesos_per_point": business.pesos_per_point,
        },
        "rewards": rewards_for_balance(business, pass_obj.balance),
    }

def apply_movement(db: Session, pass_obj: models.Pass, business: models.Business, points: int,
                   kind: str, description: str, sale_amount: float | None = None,
                   reward: models.Reward | None = None) -> dict:
    """Guarda el movimiento, actualiza el saldo y la tarjeta en Wallet, y devuelve el pase actualizado."""
    pass_obj.balance += points
    db.add(models.Transaction(
        pass_id=pass_obj.id,
        points=points,
        kind=kind,
        description=description,
        sale_amount=sale_amount,
        reward_id=reward.id if reward else None,
    ))
    db.commit()
    db.refresh(pass_obj)

    synced = update_google_wallet_pass(
        issuer_id=MI_ISSUER_ID,
        pass_id=pass_obj.id,
        design=card_design(business),
        user_name=pass_obj.user.name,
        balance=pass_obj.balance
    )
    return {
        "status": "ok",
        "points_added": points,
        "new_balance": pass_obj.balance,
        "google_wallet_synced": synced,
        **pass_summary(pass_obj, business),
    }

@router.get("/{pass_id}")
def get_pass_info(
    pass_id: str,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    return pass_summary(get_business_pass(pass_id, business, db), business)

@router.post("/{pass_id}/sumar-puntos")
def add_points(
    pass_id: str,
    data: AddPointsRequest,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    """Suma puntos por una compra (con el monto, si el comercio usa ese modo) o hace un ajuste manual."""
    pass_obj = get_business_pass(pass_id, business, db)
    if pass_obj.status != "active":
        raise HTTPException(status_code=400, detail="El pase no está activo")

    if data.amount is not None:
        try:
            points = points_for_amount(business, data.amount)
        except ProgramError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return apply_movement(db, pass_obj, business, points, "earn",
                              data.description or "Compra en local", sale_amount=data.amount)

    if not data.points:
        raise HTTPException(status_code=400, detail="La cantidad de puntos no puede ser 0")
    if pass_obj.balance + data.points < 0:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para el canje")

    # En modo "por monto" los puntos a mano son ajustes; en modo fijo, una compra normal
    is_purchase = data.points > 0 and business.points_mode == "fixed"
    kind = "earn" if is_purchase else "adjust"
    description = data.description or ("Compra en local" if is_purchase else "Ajuste manual")
    return apply_movement(db, pass_obj, business, data.points, kind, description)

@router.post("/{pass_id}/canjear")
def redeem_reward(
    pass_id: str,
    data: RedeemRequest,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    pass_obj = get_business_pass(pass_id, business, db)
    if pass_obj.status != "active":
        raise HTTPException(status_code=400, detail="El pase no está activo")

    reward = next((r for r in business.active_rewards if r.id == data.reward_id), None)
    if not reward:
        raise HTTPException(status_code=404, detail="Premio no encontrado")
    if pass_obj.balance < reward.points_cost:
        missing = reward.points_cost - pass_obj.balance
        raise HTTPException(status_code=400, detail=f"Le faltan {missing} puntos para canjear {reward.name}")

    return apply_movement(db, pass_obj, business, -reward.points_cost, "redeem",
                          f"Canje: {reward.name}", reward=reward)
