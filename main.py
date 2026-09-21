from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import engine, Base
from routers import businesses, passes

# Crear tablas
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Sello API - Plataforma de Fidelidad")

# Servir frontend estático
app.mount("/static", StaticFiles(directory="static"), name="static")

# Incluir los módulos separados
app.include_router(businesses.router)
app.include_router(passes.router)

@app.get("/")
def read_root():
    return FileResponse("static/index.html")