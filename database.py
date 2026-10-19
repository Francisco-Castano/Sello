"""
Configuración de la base de datos y la sesión.
Establece la conexión con SQLite (sello.db) y provee la dependencia de sesión para SQLAlchemy.
"""

from sqlalchemy import create_engine, inspect, text
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

# Columnas agregadas a tablas que ya existían: create_all crea tablas nuevas pero no agrega columnas.
# Es una solución temporal hasta sumar migraciones con Alembic (al pasar a Postgres).
ADDED_COLUMNS = {
    "businesses": {
        "status": "VARCHAR NOT NULL DEFAULT 'active'",
        "contact_email": "VARCHAR",
    },
}

def setup_database():
    """Crea las tablas que falten y agrega las columnas nuevas en bases existentes.
    Los modelos tienen que estar importados antes de llamarla."""
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table, columns in ADDED_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))

# Dependencia para inyectar la sesión en las rutas de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()