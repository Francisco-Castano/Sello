"""
Definición de modelos de datos y esquemas (ORM y Pydantic).
Estructura las tablas de la base de datos (comercios, usuarios, pases/tarjetas) y sus validaciones.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, LargeBinary, Boolean
from sqlalchemy.orm import relationship
from database import Base

class Business(Base):
    """El comercio que te contrata a ti (Super Admin -> Comercio)."""
    __tablename__ = "businesses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)                     # Ej: Cafetería Roma
    slug = Column(String, unique=True, index=True, nullable=False) # Ej: cafeteria-roma (para su link)
    status = Column(String, nullable=False, default="active", server_default="active")  # pending, active, suspended
    contact_email = Column(String, nullable=True)             # Para avisarle cuando se aprueba el alta
    brand_color = Column(String, nullable=True)               # Color de fondo de la tarjeta, ej: #1E3A8A
    reward_text = Column(String, nullable=True)               # Ej: Juntá 100 puntos y llevate un café
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    passes = relationship("Pass", back_populates="business")
    pos_credential = relationship("PosCredential", back_populates="business", uselist=False)
    images = relationship("BusinessImage", back_populates="business", cascade="all, delete-orphan")

    def get_image(self, kind: str):
        return next((img for img in self.images if img.kind == kind), None)


class BusinessImage(Base):
    """Logo o imagen de portada de la tarjeta del comercio.
    Se guarda en la base (no en disco) para que no se pierda al publicar el servidor."""
    __tablename__ = "business_images"

    business_id = Column(String, ForeignKey("businesses.id"), primary_key=True)
    kind = Column(String, primary_key=True)        # logo, hero
    content = Column(LargeBinary, nullable=False)
    content_type = Column(String, nullable=False)  # image/png, image/jpeg
    sha256 = Column(String, nullable=False)        # Versión de la imagen, para que Google y los navegadores no usen una vieja
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="images")


class PosCredential(Base):
    """Clave compartida del comercio para entrar a la caja (/pos).
    Vive en su propia tabla para que create_all la agregue en bases existentes sin migraciones."""
    __tablename__ = "pos_credentials"

    business_id = Column(String, ForeignKey("businesses.id"), primary_key=True)
    password_hash = Column(String, nullable=False)  # Formato: scrypt$<salt>$<hash>
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="pos_credential")


class User(Base):
    """El cliente final que visita los comercios."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, index=True, nullable=True)   # Solo dígitos; identifica al cliente entre comercios
    birthday = Column(String, nullable=True)             # "MM-DD", para encontrar rápido los cumpleaños del día
    birth_year = Column(Integer, nullable=True)          # Año de nacimiento, para saber la edad
    created_at = Column(DateTime, default=datetime.utcnow)

    passes = relationship("Pass", back_populates="user")


class Pass(Base):
    """La credencial física/digital que vive en la Wallet y porta el QR."""
    __tablename__ = "passes"

    # Este ID exacto es el que viaja codificado dentro del código QR
    id = Column(String, primary_key=True, index=True)
    business_id = Column(String, ForeignKey("businesses.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    pass_type = Column(String, default="loyalty")   # loyalty, access, coupon
    balance = Column(Integer, default=0)            # Saldo actual de puntos/sellos
    status = Column(String, default="active")       # active, suspended
    extra_data = Column(JSON, default=dict)         # Metadatos flexibles para Google/Apple
    # Consentimientos del cliente con este comercio
    privacy_accepted_at = Column(DateTime, nullable=True)
    privacy_version = Column(String, nullable=True)     # Versión de la política que aceptó
    marketing_opt_in = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    business = relationship("Business", back_populates="passes")
    user = relationship("User", back_populates="passes")
    transactions = relationship("Transaction", back_populates="pass_rel")


class Transaction(Base):
    """Libro contable de puntos (auditoría de cada escaneo en caja)."""
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    pass_id = Column(String, ForeignKey("passes.id"), nullable=False)
    points = Column(Integer, nullable=False)        # +10 por compra, -50 por premio
    description = Column(String, nullable=True)     # "Compra café", "Canje alfajor"
    created_at = Column(DateTime, default=datetime.utcnow)

    pass_rel = relationship("Pass", back_populates="transactions")