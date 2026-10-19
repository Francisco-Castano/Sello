"""
Punto de entrada principal de la aplicación FastAPI.
Configura la app, los middlewares, las rutas generales y los routers del sistema.
"""

# main.py
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import auth, businesses, passes

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sello API - Plataforma de Fidelidad")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(businesses.public_router)
app.include_router(passes.router)

# Las páginas se revalidan en cada visita para que nadie quede usando una versión vieja
NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}

def html_page(path: str) -> FileResponse:
    return FileResponse(path, headers=NO_CACHE_HEADERS)

# Ruta del cliente (Registro y guardado en Google Wallet)
# Cada comercio comparte su link /c/{slug}; sin slug la página pide el link del comercio
@app.get("/")
def read_root():
    return html_page("static/index.html")

@app.get("/c/{slug}")
def read_business_signup(slug: str):
    return html_page("static/index.html")

# Ruta del comerciante / POS (Lector QR y carga de puntos)
@app.get("/pos")
def read_pos():
    return html_page("static/pos.html")