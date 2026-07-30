import time
import jwt # PyJWT
from google.oauth2 import service_account

def generate_google_wallet_url(issuer_id: str, pass_id: str, user_name: str) -> str:
    # Cargar credenciales de la Cuenta de Servicio de Google
    credentials = service_account.Credentials.from_service_account_file(
        'google_credentials.json'
    )
    
    # Estructura del pase según la API de Google Wallet
    payload = {
        "iss": credentials.service_account_email,
        "aud": "google",
        "typ": "savetowallet",
        "iat": int(time.time()),
        "payload": {
            "genericObjects": [
                {
                    "id": f"{issuer_id}.{pass_id}",
                    "classId": f"{issuer_id}. loyalty_class_01",
                    "cardTitle": "Tarjeta de Fidelidad",
                    "header": user_name,
                    "barcode": {
                        "type": "QR_CODE",
                        "value": pass_id
                    }
                }
            ]
        }
    }

    # Firmar el JWT
    token = jwt.encode(payload, credentials.private_key, algorithm='RS256')
    return f"https://pay.google.com/gp/v/save/{token}"