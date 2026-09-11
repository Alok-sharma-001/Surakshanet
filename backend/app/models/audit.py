import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class AuditActorType(str, enum.Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"


class AuditResult(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    actor_type = Column(Enum(AuditActorType), nullable=False, default=AuditActorType.USER)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    source = Column(String(32), default="manual", nullable=False)
    result = Column(Enum(AuditResult), nullable=False, default=AuditResult.SUCCESS)
    correlation_id = Column(String(64), nullable=True)
