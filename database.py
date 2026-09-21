from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Base de datos local para desarrollo
SQLALCHEMY_DATABASE_URL = "sqlite:///./sello.db"

# Para SQLite necesitamos check_same_thread=False en FastAPI
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependencia para inyectar la sesión en las rutas de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()