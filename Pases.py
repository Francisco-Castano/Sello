import uuid
from sqlalchemy import Column, String, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Pass(Base):
    __tablename__ = 'passes'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(String, nullable=False)
    pass_type = Column(String, nullable=False) # 'LOYALTY', 'ACCESS_KEY', etc.
    serial_number = Column(String, unique=True, nullable=False)
    
    # Aquí guardas cualquier dato variable (puntos, ID de puerta, etc.)
    pass_metadata = Column(JSON, default={})