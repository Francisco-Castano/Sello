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
    points: int
    description: str = "Compra en local"

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

@router.get("/{pass_id}")
def get_pass_info(
    pass_id: str,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    pass_obj = get_business_pass(pass_id, business, db)
    birthday = pass_obj.user.birthday
    birth_year = pass_obj.user.birth_year
    today = date.today()

    return {
        "pass_id": pass_obj.id,
        "client_name": format_person_name(pass_obj.user.name),
        "birthday": birthday,
        "birthday_today": birthday == today.strftime("%m-%d"),
        "age": age_on(birth_year, birthday, today) if birthday and birth_year else None,
        "business": pass_obj.business.name,
        "balance": pass_obj.balance,
        "status": pass_obj.status
    }

@router.post("/{pass_id}/sumar-puntos")
def add_points(
    pass_id: str,
    data: AddPointsRequest,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    # 1. Buscar el pase dentro del comercio logueado
    pass_obj = get_business_pass(pass_id, business, db)

    if data.points == 0:
        raise HTTPException(status_code=400, detail="La cantidad de puntos no puede ser 0")
    if pass_obj.status != "active":
        raise HTTPException(status_code=400, detail="El pase no está activo")
    if pass_obj.balance + data.points < 0:
        raise HTTPException(status_code=400, detail="Saldo insuficiente para el canje")

    # 2. Actualizar el saldo y guardar la transacción contable
    pass_obj.balance += data.points
    tx = models.Transaction(
        pass_id=pass_obj.id,
        points=data.points,
        description=data.description
    )
    db.add(tx)
    db.commit()
    db.refresh(pass_obj)

    # 3. Sincronizar en vivo con Google Wallet
    push_success = update_google_wallet_pass(
        issuer_id=MI_ISSUER_ID,
        pass_id=pass_obj.id,
        design=card_design(business),
        user_name=pass_obj.user.name,
        balance=pass_obj.balance
    )

    return {
        "status": "ok",
        "pass_id": pass_obj.id,
        "points_added": data.points,
        "new_balance": pass_obj.balance,
        "google_wallet_synced": push_success
    }