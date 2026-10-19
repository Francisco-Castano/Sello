"""
Enrutador de FastAPI para la gestión de comercios.
Maneja los endpoints de registro, configuración de perfiles de negocios y administración de locales.
"""

import re
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import require_admin

router = APIRouter(
    prefix="/businesses",
    tags=["Comercios (Admin)"],
    dependencies=[Depends(require_admin)]
)

# Datos públicos del comercio, para la página de registro de clientes (/c/{slug})
public_router = APIRouter(
    prefix="/public/businesses",
    tags=["Comercios (público)"]
)

class BusinessCreate(BaseModel):
    name: str = Field(..., example="Pizzería Nápoles")
    slug: str | None = Field(None, example="pizzeria-napoles")

def generate_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    return re.sub(r"[\s_-]+", "-", slug)

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

    return {"name": business.name, "slug": business.slug}
