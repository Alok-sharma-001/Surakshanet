import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class SignalMode(str, enum.Enum):
    MARL = "MARL"
    WEBSTER = "WEBSTER"
    MANUAL = "MANUAL"

class SignalPlan(Base):
    __tablename__ = "signal_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    junction_id = Column(UUID(as_uuid=True), ForeignKey("junctions.id"), nullable=False)
    name = Column(String, nullable=False)
    phases = Column(JSON, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    mode = Column(Enum(SignalMode), default=SignalMode.WEBSTER, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, onupdate=datetime.utcnow, nullable=True)
