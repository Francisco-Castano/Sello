"""
Enrutador de FastAPI para el acceso a la caja.
Valida la clave del comercio y entrega el token de sesión que usa el POS.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import create_pos_token, verify_password, get_current_business, TOKEN_DURATION_SECONDS

router = APIRouter(
    prefix="/auth",
    tags=["Acceso a caja"]
)

class PosLoginRequest(BaseModel):
    business_slug: str
    password: str

@router.post("/login")
def pos_login(data: PosLoginRequest, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.slug == data.business_slug.strip()).first()
    credential = business.pos_credential if business else None

    # Mismo mensaje si el comercio no existe, no tiene clave o la clave es incorrecta
    if not credential or not verify_password(data.password, credential.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Comercio o clave incorrectos"
        )

    if business.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu comercio todavía está pendiente de aprobación"
        )
    if business.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tu comercio está suspendido"
        )

    return {
        "access_token": create_pos_token(business),
        "token_type": "bearer",
        "expires_in": TOKEN_DURATION_SECONDS,
        "business": business.name,
        "business_slug": business.slug
    }

@router.get("/me")
def pos_me(business: models.Business = Depends(get_current_business)):
    return {"business": business.name, "business_slug": business.slug}
