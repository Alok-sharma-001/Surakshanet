import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class AlertType(str, enum.Enum):
    CONGESTION = "CONGESTION"
    SPILLBACK = "SPILLBACK"
    SIGNAL_FAILURE = "SIGNAL_FAILURE"
    QUEUE_OVERFLOW = "QUEUE_OVERFLOW"

class AlertSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"

class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    junction_id = Column(UUID(as_uuid=True), ForeignKey("junctions.id"), nullable=True)
    alert_type = Column(Enum(AlertType), nullable=False)
    severity = Column(Enum(AlertSeverity), nullable=False)
    message = Column(String, nullable=False)
    is_acknowledged = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)

class EmergencyPriority(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"

class EmergencyVehicleType(str, enum.Enum):
    AMBULANCE = "AMBULANCE"
    FIRE = "FIRE"
    POLICE = "POLICE"
    VIP = "VIP"

class EmergencyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class EmergencyEvent(Base):
    __tablename__ = "emergency_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    priority = Column(Enum(EmergencyPriority), nullable=False)
    vehicle_type = Column(Enum(EmergencyVehicleType), nullable=False)
    route = Column(JSON, nullable=False)
    status = Column(Enum(EmergencyStatus), nullable=False)
    activated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
