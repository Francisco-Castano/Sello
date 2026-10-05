"""
Punto de entrada principal de la aplicación FastAPI.
Configura la app, los middlewares, las rutas generales y los routers del sistema.
"""

# main.py
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import businesses, passes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sello API - Plataforma de Fidelidad")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(businesses.router)
app.include_router(passes.router)

# Ruta del cliente (Registro y guardado en Google Wallet)
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# Ruta del comerciante / POS (Lector QR y carga de puntos)
@app.get("/pos")
def read_pos():
    return FileResponse("static/pos.html")