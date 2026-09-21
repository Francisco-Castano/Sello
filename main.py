import os
import uuid
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from GoogleWallet import MI_ISSUER_ID, generate_google_wallet_url

app = FastAPI(title="Sello API - Pases de Fidelidad")

# Servir la carpeta static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ruta principal: entrega el archivo HTML al entrar a http://127.0.0.1:8000
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

class UserRegisterRequest(BaseModel):
    name: str
    phone: str

@app.post("/crear-pase-google")
def create_pass(data: UserRegisterRequest):
    unique_pass_id = f"user_{uuid.uuid4().hex[:8]}"
    
    wallet_url = generate_google_wallet_url(
        issuer_id=MI_ISSUER_ID,
        pass_id=unique_pass_id,
        user_name=data.name
    )
    
    return {
        "status": "ok",
        "client_name": data.name,
        "pass_id": unique_pass_id,
        "wallet_url": wallet_url
    }