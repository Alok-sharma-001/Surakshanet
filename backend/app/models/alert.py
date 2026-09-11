import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Enum, JSON, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
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
    vehicle_id = Column(String(64), nullable=True)
    priority = Column(Enum(EmergencyPriority), nullable=False)
    vehicle_type = Column(Enum(EmergencyVehicleType), nullable=False)
    origin_lat = Column(Float, nullable=True)
    origin_lon = Column(Float, nullable=True)
    destination_lat = Column(Float, nullable=True)
    destination_lon = Column(Float, nullable=True)
    destination_name = Column(String(128), nullable=True)
    route = Column(JSON, nullable=False)
    route_etas = Column(JSON, nullable=True)
    captured_programs = Column(JSON, nullable=True)
    status = Column(Enum(EmergencyStatus), nullable=False)
    activated_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    restored_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    clearance_time_s = Column(Float, nullable=True)
    cross_street_max_red_s = Column(Float, nullable=True)
    recovery_s = Column(Float, nullable=True)
    recovery_series = Column(JSON, nullable=True)

    @validates("status")
    def validate_status(self, key, value):
        is_completed = (
            value == EmergencyStatus.COMPLETED
            or (isinstance(value, str) and value.upper() == "COMPLETED")
            or (hasattr(value, "name") and value.name == "COMPLETED")
        )
        if is_completed and self.restored_at is None:
            raise ValueError(
                "EmergencyEvent status cannot become COMPLETED before restored_at is set."
            )
        return value
