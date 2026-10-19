"""
Enrutador de FastAPI para la gestión de comercios.
Maneja los endpoints de registro, configuración de perfiles de negocios y administración de locales.
"""

import re
import unicodedata
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import require_admin, hash_password, MIN_PASSWORD_LENGTH

router = APIRouter(
    prefix="/businesses",
    tags=["Comercios (Admin)"],
    dependencies=[Depends(require_admin)]
)

# Endpoints públicos: datos del comercio para /c/{slug} y alta de comercios nuevos desde /alta
public_router = APIRouter(
    prefix="/public/businesses",
    tags=["Comercios (público)"]
)

class BusinessCreate(BaseModel):
    name: str = Field(..., example="Pizzería Nápoles")
    slug: str | None = Field(None, example="pizzeria-napoles")

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def generate_slug(name: str) -> str:
    # Saca tildes y eñes para que el link sea simple de tipear: "Café Ñandú" -> "cafe-nandu"
    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = slug.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    return re.sub(r"[\s_-]+", "-", slug).strip("-")

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_business(data: BusinessCreate, db: Session = Depends(get_db)):
    slug = data.slug or generate_slug(data.name)

    existing = db.query(models.Business).filter(models.Business.slug == slug).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un comercio con el slug '{slug}'"
        )

    new_business = models.Business(name=data.name, slug=slug)
    db.add(new_business)
    db.commit()
    db.refresh(new_business)

    return {
        "status": "ok",
        "id": new_business.id,
        "name": new_business.name,
        "slug": new_business.slug
    }

@router.get("/")
def list_businesses(db: Session = Depends(get_db)):
    businesses = db.query(models.Business).all()
    return [
        {"id": b.id, "name": b.name, "slug": b.slug, "created_at": b.created_at}
        for b in businesses
    ]
@public_router.get("/{slug}")
def get_public_business(slug: str, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.slug == slug).first()
    if not business:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")

    return {"name": business.name, "slug": business.slug, "active": business.status == "active"}


class BusinessSignup(BaseModel):
    name: str = Field(..., min_length=2, max_length=80, example="Cafetería Roma")
    slug: str | None = Field(None, example="cafeteria-roma")
    contact_email: str = Field(..., example="hola@cafeteriaroma.com")
    password: str

@public_router.post("/alta", status_code=status.HTTP_201_CREATED)
def signup_business(data: BusinessSignup, db: Session = Depends(get_db)):
    """Alta de un comercio nuevo. Queda pendiente hasta que el Super Admin lo apruebe con admin.py."""
    name = data.name.strip()
    slug = (data.slug or "").strip().lower() or generate_slug(name)
    email = data.contact_email.strip().lower()

    if not 3 <= len(slug) <= 40 or not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=400,
            detail="El link tiene que tener entre 3 y 40 caracteres: solo letras, números y guiones"
        )
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(status_code=400, detail="El email no es válido")
    if len(data.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"La clave de caja tiene que tener al menos {MIN_PASSWORD_LENGTH} caracteres"
        )
    if db.query(models.Business).filter(models.Business.slug == slug).first():
        raise HTTPException(status_code=409, detail=f"El link '{slug}' ya está en uso, elegí otro")

    business = models.Business(name=name, slug=slug, contact_email=email, status="pending")
    db.add(business)
    db.flush()
    db.add(models.PosCredential(business_id=business.id, password_hash=hash_password(data.password)))
    db.commit()

    return {"status": "pending", "name": business.name, "slug": business.slug}
