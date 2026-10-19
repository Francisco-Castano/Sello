"""
Seguridad de la API.
Hashea las claves de caja, emite y valida los tokens de sesión del POS y protege los endpoints de administración.
"""

import base64
import hashlib
import hmac
import os
import secrets
import time
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from database import get_db
import models

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY_PATH = os.path.join(BASE_DIR, ".secret_key")

TOKEN_ALGORITHM = "HS256"
TOKEN_DURATION_SECONDS = 12 * 60 * 60  # Un turno de caja


def _load_secret_key() -> str:
    """Usa SELLO_SECRET_KEY si está definida; si no, crea una clave local en .secret_key (ignorada por git)."""
    env_key = os.environ.get("SELLO_SECRET_KEY")
    if env_key:
        return env_key

    if not os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "w", encoding="utf-8") as f:
            f.write(secrets.token_urlsafe(48))

    with open(SECRET_KEY_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


SECRET_KEY = _load_secret_key()


# --- Claves de caja ---

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt${}${}".format(
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode()
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, salt_b64, digest_b64 = stored_hash.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except ValueError:
        return False

    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return hmac.compare_digest(digest, expected)


# --- Sesión del POS ---

def _credential_version(credential: models.PosCredential) -> str:
    """Cambia cada vez que se cambia la clave, así las sesiones viejas dejan de valer."""
    return hashlib.sha256(credential.password_hash.encode()).hexdigest()[:16]


def create_pos_token(business: models.Business) -> str:
    now = int(time.time())
    payload = {
        "sub": business.id,
        "scope": "pos",
        "ver": _credential_version(business.pos_credential),
        "iat": now,
        "exp": now + TOKEN_DURATION_SECONDS
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=TOKEN_ALGORITHM)


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_business(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> models.Business:
    """Dependencia: devuelve el comercio dueño del token o responde 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesión de caja inválida o vencida",
        headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[TOKEN_ALGORITHM])
    except jwt.PyJWTError:
        raise unauthorized

    if payload.get("scope") != "pos":
        raise unauthorized

    business = db.query(models.Business).filter(models.Business.id == payload.get("sub")).first()
    if not business or not business.pos_credential:
        raise unauthorized

    if payload.get("ver") != _credential_version(business.pos_credential):
        raise unauthorized

    return business


# --- Administración (Super Admin) ---

def require_admin(x_admin_key: str | None = Header(None)) -> None:
    """Dependencia: exige el header X-Admin-Key igual a SELLO_ADMIN_KEY. Sin esa variable, la administración queda cerrada."""
    admin_key = os.environ.get("SELLO_ADMIN_KEY")
    if not admin_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administración por API deshabilitada: definí SELLO_ADMIN_KEY o usá admin.py"
        )

    if not x_admin_key or not hmac.compare_digest(x_admin_key, admin_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Clave de administración inválida")
