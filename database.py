"""
Configuración de la base de datos y la sesión.
Establece la conexión con SQLite (sello.db) y provee la dependencia de sesión para SQLAlchemy.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
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
        "brand_color": "VARCHAR",
        "reward_text": "VARCHAR",
    },
    "users": {
        "birthday": "VARCHAR",
        "birth_year": "INTEGER",
    },
    "passes": {
        "privacy_accepted_at": "DATETIME",
        "privacy_version": "VARCHAR",
        "marketing_opt_in": "BOOLEAN NOT NULL DEFAULT 0",
    },
}

def setup_database():
    """Crea las tablas que falten y agrega las columnas nuevas en bases existentes.
    Los modelos tienen que estar importados antes de llamarla."""
    # Si dos servidores arrancan a la vez, uno puede crear una tabla mientras el otro también la está creando:
    # al reintentar, create_all ya la ve y sigue con las que falten
    for attempt in range(3):
        try:
            Base.metadata.create_all(bind=engine)
            break
        except OperationalError:
            if attempt == 2:
                raise

    for table, columns in ADDED_COLUMNS.items():
        for name, definition in columns.items():
            if _has_column(table, name):
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
            except OperationalError:
                # Si dos servidores arrancan a la vez, el otro pudo haberla agregado primero
                if not _has_column(table, name):
                    raise

def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(engine).get_columns(table)}

# Dependencia para inyectar la sesión en las rutas de FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()