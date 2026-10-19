"""
Enrutador de FastAPI para la personalización de las tarjetas.
La caja edita la marca de su comercio y se sirven el logo y la portada que descarga Google Wallet.
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
import models
from auth import get_current_business
from branding import (
    IMAGE_KINDS, BrandingError, branding_info, clean_color, clean_reward_text,
    remove_image, set_image, sync_business_passes
)

router = APIRouter(tags=["Personalización de tarjetas"])


class BrandingUpdate(BaseModel):
    brand_color: str | None = None
    reward_text: str | None = None
    logo: str | None = None          # Imagen nueva como data URL; si no viene, se mantiene la actual
    hero: str | None = None
    remove_logo: bool = False
    remove_hero: bool = False


@router.get("/branding")
def get_branding(business: models.Business = Depends(get_current_business)):
    return {"name": business.name, "slug": business.slug, **branding_info(business)}


@router.put("/branding")
def update_branding(
    data: BrandingUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    business: models.Business = Depends(get_current_business)
):
    try:
        business.brand_color = clean_color(data.brand_color)
        business.reward_text = clean_reward_text(data.reward_text)
        for kind, new_image, remove in (("logo", data.logo, data.remove_logo), ("hero", data.hero, data.remove_hero)):
            if new_image:
                set_image(business, kind, new_image)
            elif remove:
                remove_image(business, kind)
    except BrandingError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    db.refresh(business)

    # Las tarjetas que los clientes ya tienen se actualizan después de responder
    passes_count = len(business.passes)
    if passes_count:
        background_tasks.add_task(sync_business_passes, business.id)

    return {
        "status": "ok",
        "name": business.name,
        "slug": business.slug,
        "passes_to_update": passes_count,
        **branding_info(business)
    }


@router.get("/media/{slug}/{kind}")
def get_business_image(slug: str, kind: str, db: Session = Depends(get_db)):
    """Imagen pública del comercio. La URL lleva ?v=<versión>, así que se puede guardar en caché mucho tiempo."""
    if kind not in IMAGE_KINDS:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    business = db.query(models.Business).filter(models.Business.slug == slug).first()
    image = business.get_image(kind) if business else None
    if not image:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")

    return Response(
        content=image.content,
        media_type=image.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable", "ETag": f'"{image.sha256}"'}
    )
