import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models
from GoogleWallet import MI_ISSUER_ID, generate_google_wallet_url

router = APIRouter(
    prefix="/passes",
    tags=["Pases & Fidelidad"]
)

class UserRegisterRequest(BaseModel):
    name: str
    phone: str
    business_slug: str = "demo-cafe"

class AddPointsRequest(BaseModel):
    points: int
    description: str = "Compra en local"

@router.post("/crear-google")
def create_pass(data: UserRegisterRequest, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.slug == data.business_slug).first()
    if not business:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    user = None
    if data.phone and data.phone != "N/A":
        user = db.query(models.User).filter(models.User.phone == data.phone).first()

    if not user:
        user = models.User(name=data.name, phone=data.phone)
        db.add(user)
        db.commit()
        db.refresh(user)

    unique_pass_id = f"sello_{uuid.uuid4().hex[:8]}"

    new_pass = models.Pass(
        id=unique_pass_id,
        business_id=business.id,
        user_id=user.id,
        balance=0,
        pass_type="loyalty"
    )
    db.add(new_pass)
    db.commit()
    db.refresh(new_pass)

    wallet_url = generate_google_wallet_url(
        issuer_id=MI_ISSUER_ID,
        pass_id=unique_pass_id,
        user_name=user.name
    )

    return {
        "status": "ok",
        "business": business.name,
        "client_name": user.name,
        "pass_id": new_pass.id,
        "balance": new_pass.balance,
        "wallet_url": wallet_url
    }

@router.post("/{pass_id}/sumar-puntos")
def add_points(pass_id: str, data: AddPointsRequest, db: Session = Depends(get_db)):
    pass_obj = db.query(models.Pass).filter(models.Pass.id == pass_id).first()
    if not pass_obj:
        raise HTTPException(status_code=404, detail="Pase no encontrado")

    pass_obj.balance += data.points
    tx = models.Transaction(
        pass_id=pass_obj.id,
        points=data.points,
        description=data.description
    )
    db.add(tx)
    db.commit()
    db.refresh(pass_obj)

    return {
        "status": "ok",
        "pass_id": pass_obj.id,
        "points_added": data.points,
        "new_balance": pass_obj.balance
    }

@router.get("/{pass_id}")
def get_pass_info(pass_id: str, db: Session = Depends(get_db)):
    pass_obj = db.query(models.Pass).filter(models.Pass.id == pass_id).first()
    if not pass_obj:
        raise HTTPException(status_code=404, detail="Pase no encontrado")

    return {
        "pass_id": pass_obj.id,
        "client_name": pass_obj.user.name,
        "business": pass_obj.business.name,
        "balance": pass_obj.balance,
        "status": pass_obj.status
    }