"""
Punto de entrada principal de la aplicación FastAPI.
Configura la app, los middlewares, las rutas generales y los routers del sistema.
"""

# main.py
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import setup_database
from routers import auth, branding, businesses, passes, program

setup_database()

app = FastAPI(title="Sello API - Plataforma de Fidelidad")

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(businesses.router)
app.include_router(businesses.public_router)
app.include_router(passes.router)
app.include_router(branding.router)
app.include_router(program.router)

# Las páginas se revalidan en cada visita para que nadie quede usando una versión vieja
NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}

@app.middleware("http")
async def revalidate_static_files(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response

def html_page(path: str) -> FileResponse:
    return FileResponse(path, headers=NO_CACHE_HEADERS)

# Página institucional de Sello: qué es, cómo funciona y acceso al alta y a la caja
@app.get("/")
def read_root():
    return html_page("static/home.html")

# Ruta del cliente (Registro y guardado en Google Wallet)
# Cada comercio comparte su link /c/{slug}
@app.get("/c/{slug}")
def read_business_signup(slug: str):
    return html_page("static/index.html")

# Alta de comercios nuevos (quedan pendientes hasta que el Super Admin los apruebe)
@app.get("/alta")
def read_business_onboarding():
    return html_page("static/alta.html")

# Política de privacidad que aceptan los clientes al registrarse
@app.get("/privacidad")
def read_privacy_policy():
    return html_page("static/privacidad.html")

# Ruta del comerciante / POS (Lector QR y carga de puntos)
@app.get("/pos")
def read_pos():
    return html_page("static/pos.html")