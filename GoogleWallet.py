import json
import os
import time
import jwt

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'sello-proyecto-inicial-3d27f739fa4b.json')

# Pega aquí tu Issuer ID numérico
MI_ISSUER_ID = "3388000000023143752"

def generate_google_wallet_url(issuer_id: str, pass_id: str, user_name: str) -> str:
    with open(CREDENTIALS_PATH, 'r', encoding='utf-8') as f:
        credentials_info = json.load(f)

    client_email = credentials_info["client_email"]
    private_key = credentials_info["private_key"]
    
    # Usamos identificadores nuevos para evitar registros previos corruptos
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

if __name__ == "__main__":
    url = generate_google_wallet_url(MI_ISSUER_ID, "test_user_002", "Franco")
    print("\nNueva URL generada:\n", url)