import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base

class Business(Base):
    """El comercio que te contrata a ti (Super Admin -> Comercio)."""
    __tablename__ = "businesses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)                     # Ej: Cafetería Roma
    slug = Column(String, unique=True, index=True, nullable=False) # Ej: cafeteria-roma (para su link)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relaciones
    passes = relationship("Pass", back_populates="business")


class User(Base):
    """El cliente final que visita los comercios."""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    phone = Column(String, index=True, nullable=True)
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