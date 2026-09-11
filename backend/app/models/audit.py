import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, JSON, Float, CheckConstraint, PrimaryKeyConstraint
from sqlalchemy.orm import validates
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
    timestamp = Column(DateTime, primary_key=True, default=datetime.utcnow, nullable=False, index=True)
    actor_type = Column(Enum(AuditActorType), nullable=False, default=AuditActorType.USER)
    actor_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True)
    target_id = Column(UUID(as_uuid=True), nullable=True)
    input = Column(JSON, nullable=True)
    output = Column(JSON, nullable=True)
    model = Column(String(64), nullable=True)
    model_version = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    source = Column(String(32), default="manual", nullable=False)
    result = Column(Enum(AuditResult), nullable=False, default=AuditResult.SUCCESS)
    correlation_id = Column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(confidence IS NULL) OR (actor_type = 'AI')",
            name="ck_audit_logs_confidence_actor_ai",
        ),
        PrimaryKeyConstraint("id", "timestamp"),
    )

    @validates("confidence")
    def validate_confidence(self, key, value):
        if value is not None:
            act = getattr(self, "actor_type", None)
            if act is not None:
                act_val = act.value if hasattr(act, "value") else str(act)
                if act_val != "AI":
                    raise ValueError("confidence must be null unless actor_type is 'AI'")
        return value

    def __init__(self, **kwargs):
        conf = kwargs.get("confidence")
        act = kwargs.get("actor_type")
        if conf is not None:
            act_val = act.value if hasattr(act, "value") else str(act)
            if act_val != "AI":
                raise ValueError("confidence must be null unless actor_type is 'AI'")
        super().__init__(**kwargs)
