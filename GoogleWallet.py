"""
Módulo de integración con Google Wallet.
Gestiona la lógica de creación, formato y firma de pases digitales para la billetera de Google.
"""

import json
import os
import time
from dataclasses import dataclass, field
from names import format_person_name
from program import reward_progress
import jwt
import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'google_credentials.json')

MI_ISSUER_ID = "3388000000023143752" 

SCOPES = ['https://www.googleapis.com/auth/wallet_object.issuer']

def get_google_auth_token():
    """Genera un token OAuth2 de corta duración usando la Service Account."""
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_PATH,
        scopes=SCOPES
    )
    credentials.refresh(Request())
    return credentials.token

DEFAULT_CARD_COLOR = "#1E3A8A"
CLASS_SUFFIX = "sello_generic_v2"
WALLET_API = "https://walletobjects.googleapis.com/walletobjects/v1"

# Plantilla de la clase: muestra Puntos y Premio en la cara de la tarjeta (si no, solo se ven en el detalle).
# Si un comercio no tiene premio, Google deja vacío ese lugar.
CLASS_TEMPLATE_INFO = {
    "cardTemplateOverride": {
        "cardRowTemplateInfos": [
            {
                "twoItems": {
                    "startItem": {"firstValue": {"fields": [{"fieldPath": "object.textModulesData['balance_module']"}]}},
                    "endItem": {"firstValue": {"fields": [{"fieldPath": "object.textModulesData['reward_module']"}]}}
                }
            }
        ]
    }
}


@dataclass
class CardDesign:
    """Cómo se ve la tarjeta de un comercio. Las imágenes tienen que ser URLs públicas con https."""
    business_name: str
    color: str = DEFAULT_CARD_COLOR
    reward_text: str | None = None          # Texto libre, si el comercio no cargó premios
    rewards: list[tuple[str, int]] = field(default_factory=list)  # (nombre, puntos) de cada premio
    logo_url: str | None = None
    hero_url: str | None = None


def _text(value: str) -> dict:
    return {"defaultValue": {"language": "es", "value": value}}


def _image(url: str, description: str) -> dict:
    return {"sourceUri": {"uri": url}, "contentDescription": _text(description)}


def build_visual_fields(design: CardDesign, user_name: str, balance: int) -> dict:
    """Campos visibles de la tarjeta. Se usan igual al crearla y al actualizarla."""
    text_modules = [
        {"id": "balance_module", "header": "Puntos", "body": f"{balance} pts"}
    ]
    # Con premios cargados se muestra el progreso del cliente; si no, el texto libre del comercio
    reward_line = reward_progress(design.rewards, balance) or design.reward_text
    if reward_line:
        text_modules.append({"id": "reward_module", "header": "Premio", "body": reward_line})

    fields = {
        "cardTitle": _text(design.business_name),
        "header": _text(format_person_name(user_name)),
        # Puntos y Premio se ven en la cara de la tarjeta gracias a CLASS_TEMPLATE_INFO
        "subheader": _text("Cliente"),
        "textModulesData": text_modules,
        "hexBackgroundColor": design.color,
    }
    if design.logo_url:
        fields["logo"] = _image(design.logo_url, f"Logo de {design.business_name}")
    if design.hero_url:
        fields["heroImage"] = _image(design.hero_url, f"Imagen de {design.business_name}")
    return fields


def generate_google_wallet_url(issuer_id: str, pass_id: str, user_name: str, design: CardDesign, balance: int = 0) -> str:
    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
        credentials_info = json.load(f)

    client_email = credentials_info["client_email"]
    private_key = credentials_info["private_key"]

    class_id = f"{issuer_id}.{CLASS_SUFFIX}"
    object_id = f"{issuer_id}.{pass_id}"

    payload = {
        "iss": client_email,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "genericClasses": [
                {
                    "id": class_id,
                    "classTemplateInfo": CLASS_TEMPLATE_INFO
                }
            ],
            "genericObjects": [
                {
                    "id": object_id,
                    "classId": class_id,
                    **build_visual_fields(design, user_name, balance),
                    "barcode": {
                        "type": "QR_CODE",
                        "value": pass_id,
                        "alternateText": pass_id
                    }
                }
            ]
        }
    }

    token = jwt.encode(payload, private_key, algorithm='RS256')
    return f"https://pay.google.com/gp/v/save/{token}"


def update_google_wallet_pass(issuer_id: str, pass_id: str, design: CardDesign, user_name: str, balance: int, token: str | None = None) -> bool:
    """Actualiza saldo y diseño de una tarjeta ya guardada en Wallet (PATCH: solo los campos visibles).
    Devuelve False si el cliente todavía no la guardó o si Google rechaza el cambio."""
    try:
        token = token or get_google_auth_token()
        object_id = f"{issuer_id}.{pass_id}"
        url = f"https://walletobjects.googleapis.com/walletobjects/v1/genericObject/{object_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        res = requests.patch(url, headers=headers, json=build_visual_fields(design, user_name, balance), timeout=15)

        if res.status_code == 200:
            print(f"[GoogleWallet] Pase {pass_id} actualizado ({balance} pts).")
            return True
        if res.status_code == 404:
            print(f"[GoogleWallet] El pase {pass_id} todavía no fue guardado en Wallet.")
            return False

        print(f"[GoogleWallet] Fallo PATCH para {object_id}: {res.status_code} - {res.text}")
        return False

    except Exception as e:
        print(f"[GoogleWallet] Excepción al actualizar pase: {e}")
        return False


def apply_class_template(issuer_id: str) -> str:
    """Crea la clase de tarjetas con la plantilla, o se la aplica si ya existe.
    Afecta a todas las tarjetas de todos los comercios. Devuelve un mensaje con el resultado."""
    token = get_google_auth_token()
    class_id = f"{issuer_id}.{CLASS_SUFFIX}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{WALLET_API}/genericClass/{class_id}"

    res = requests.get(url, headers=headers, timeout=15)
    if res.status_code == 404:
        res = requests.post(f"{WALLET_API}/genericClass", headers=headers, timeout=15,
                            json={"id": class_id, "classTemplateInfo": CLASS_TEMPLATE_INFO})
        action = "creada"
    elif res.status_code == 200:
        res = requests.patch(url, headers=headers, timeout=15, json={"classTemplateInfo": CLASS_TEMPLATE_INFO})
        action = "actualizada"
    else:
        raise RuntimeError(f"No se pudo leer la clase {class_id}: {res.status_code} - {res.text}")

    if res.status_code != 200:
        raise RuntimeError(f"Google rechazó la plantilla: {res.status_code} - {res.text}")
    return f"Clase {class_id} {action} con la plantilla de Puntos y Premio."
