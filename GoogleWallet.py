"""
Módulo de integración con Google Wallet.
Gestiona la lógica de creación, formato y firma de pases digitales para la billetera de Google.
"""

import json
import os
import time
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

def generate_google_wallet_url(issuer_id: str, pass_id: str, user_name: str, balance: int = 0) -> str:
    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
        credentials_info = json.load(f)

    client_email = credentials_info["client_email"]
    private_key = credentials_info["private_key"]
    
    class_id = f"{issuer_id}.sello_generic_v2"
    object_id = f"{issuer_id}.{pass_id}"

    payload = {
        "iss": client_email,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "genericClasses": [
                {
                    "id": class_id
                }
            ],
            "genericObjects": [
                {
                    "id": object_id,
                    "classId": class_id,
                    "cardTitle": {
                        "defaultValue": {
                            "language": "es",
                            "value": "Sello Loyalty"
                        }
                    },
                    "header": {
                        "defaultValue": {
                            "language": "es",
                            "value": user_name
                        }
                    },
                    "subheader": {
                        "defaultValue": {
                            "language": "es",
                            "value": "Puntos acumulados"
                        }
                    },
                    "textModulesData": [
                        {
                            "id": "balance_module",
                            "header": "Puntos",
                            "body": f"{balance} pts"
                        }
                    ],
                    "barcode": {
                        "type": "QR_CODE",
                        "value": pass_id,
                        "alternateText": pass_id
                    },
                    "hexBackgroundColor": "#1E3A8A"
                }
            ]
        }
    }

    token = jwt.encode(payload, private_key, algorithm='RS256')
    return f"https://pay.google.com/gp/v/save/{token}"

def update_google_wallet_balance(issuer_id: str, pass_id: str, new_balance: int, points_added: int) -> bool:
    """Obtiene el objeto actual de Google Wallet, actualiza los campos visibles y lo reemplaza vía PUT."""
    try:
        token = get_google_auth_token()
        object_id = f"{issuer_id}.{pass_id}"
        url = f"https://walletobjects.googleapis.com/walletobjects/v1/genericObject/{object_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        # 1. Obtener el estado actual completo del pase desde Google
        res_get = requests.get(url, headers=headers)
        if res_get.status_code != 200:
            print(f"[GoogleWallet] Error al obtener objeto {object_id}: {res_get.status_code} - {res_get.text}")
            return False

        current_object = res_get.json()

        # 2. Modificar dinámicamente los campos visibles de saldo
        current_object["textModulesData"] = [
            {
                "id": "balance_module",
                "header": "Puntos",
                "body": f"{new_balance} pts"
            }
        ]
        current_object["subheader"] = {
            "defaultValue": {
                "language": "es",
                "value": f"{new_balance} Puntos acumulados"
            }
        }

        # 3. Guardar el objeto actualizado con PUT
        res_put = requests.put(url, headers=headers, json=current_object)
        
        if res_put.status_code == 200:
            print(f"[GoogleWallet] Pase {pass_id} actualizado con éxito a {new_balance} pts.")
            return True
        else:
            print(f"[GoogleWallet] Fallo PUT para {object_id}: {res_put.status_code} - {res_put.text}")
            return False

    except Exception as e:
        print(f"[GoogleWallet] Excepción al actualizar pase: {e}")
        return False
