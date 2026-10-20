"""
Personalización de las tarjetas de cada comercio.
Valida color, premio e imágenes, arma el diseño para Google Wallet y actualiza las tarjetas ya entregadas.
"""

import base64
import binascii
import hashlib
import os
import re
from GoogleWallet import CardDesign, DEFAULT_CARD_COLOR, MI_ISSUER_ID, get_google_auth_token, update_google_wallet_pass
from database import SessionLocal
import models

# URL pública del servidor (ej: https://sello.com). Google descarga el logo y la portada desde ahí,
# así que sin una URL https pública las tarjetas salen sin imágenes (el color y el premio funcionan igual).
PUBLIC_URL = os.environ.get("SELLO_PUBLIC_URL", "").rstrip("/")

COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")
MAX_REWARD_LENGTH = 60
MAX_IMAGE_BYTES = 1_500_000
IMAGE_KINDS = ("logo", "hero")
IMAGE_SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
}


class BrandingError(ValueError):
    """Dato de personalización inválido; el mensaje se muestra tal cual al comercio."""


def clean_color(color: str | None) -> str | None:
    if color is None or color.strip() == "":
        return None
    color = color.strip().upper()
    if not COLOR_PATTERN.match(color):
        raise BrandingError("El color tiene que tener el formato #RRGGBB")
    return color


def clean_reward_text(text: str | None) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())
    if len(text) > MAX_REWARD_LENGTH:
        raise BrandingError(f"El texto del premio puede tener hasta {MAX_REWARD_LENGTH} caracteres")
    return text or None


def parse_image(data_url: str) -> tuple[bytes, str]:
    """Recibe una imagen como data URL (data:image/png;base64,...) y devuelve (bytes, tipo)."""
    match = re.match(r"^data:(image/(?:png|jpeg));base64,(.+)$", data_url, re.DOTALL)
    if not match:
        raise BrandingError("La imagen tiene que ser PNG o JPG")

    content_type, encoded = match.groups()
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise BrandingError("No se pudo leer la imagen")

    if len(content) > MAX_IMAGE_BYTES:
        raise BrandingError("La imagen es demasiado pesada (máximo 1,5 MB)")
    if not content.startswith(IMAGE_SIGNATURES[content_type]):
        raise BrandingError("El archivo no es una imagen PNG o JPG válida")
    return content, content_type


def set_image(business: models.Business, kind: str, data_url: str) -> None:
    content, content_type = parse_image(data_url)
    sha = hashlib.sha256(content).hexdigest()
    image = business.get_image(kind)
    if image:
        image.content, image.content_type, image.sha256 = content, content_type, sha
    else:
        business.images.append(models.BusinessImage(kind=kind, content=content, content_type=content_type, sha256=sha))


def remove_image(business: models.Business, kind: str) -> None:
    image = business.get_image(kind)
    if image:
        business.images.remove(image)


def image_path(business: models.Business, kind: str) -> str | None:
    """Ruta relativa de la imagen, con su versión para que nadie use una copia vieja."""
    image = business.get_image(kind)
    return f"/media/{business.slug}/{kind}?v={image.sha256[:12]}" if image else None


def card_design(business: models.Business) -> CardDesign:
    def public(kind: str) -> str | None:
        path = image_path(business, kind)
        return f"{PUBLIC_URL}{path}" if path and PUBLIC_URL.startswith("https://") else None

    return CardDesign(
        business_name=business.name,
        color=business.brand_color or DEFAULT_CARD_COLOR,
        reward_text=business.reward_text,
        rewards=[(r.name, r.points_cost) for r in business.active_rewards],
        logo_url=public("logo"),
        hero_url=public("hero"),
    )


def branding_info(business: models.Business) -> dict:
    """Lo que necesitan las páginas para mostrar la marca del comercio."""
    return {
        "brand_color": business.brand_color or DEFAULT_CARD_COLOR,
        "reward_text": business.reward_text,
        "logo_url": image_path(business, "logo"),
        "hero_url": image_path(business, "hero"),
        "images_visible_in_wallet": PUBLIC_URL.startswith("https://"),
    }


def sync_business_passes(business_id: str) -> None:
    """Aplica el diseño actual a todas las tarjetas del comercio que ya están en Wallet.
    Corre en segundo plano después de guardar, con su propia sesión de base de datos."""
    db = SessionLocal()
    try:
        business = db.get(models.Business, business_id)
        if not business or not business.passes:
            return

        design = card_design(business)
        token = get_google_auth_token()
        updated = sum(
            update_google_wallet_pass(MI_ISSUER_ID, p.id, design, p.user.name, p.balance, token=token)
            for p in business.passes
        )
        print(f"[Branding] {business.name}: {updated} de {len(business.passes)} tarjetas actualizadas en Wallet.")
    except Exception as e:
        print(f"[Branding] No se pudieron actualizar las tarjetas: {e!r}")
    finally:
        db.close()
