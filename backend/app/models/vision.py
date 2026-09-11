import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
from app.database import Base


class BehaviorFlagType(str, enum.Enum):
    WRONG_WAY = "WRONG_WAY"
    ILLEGAL_PARKING = "ILLEGAL_PARKING"
    DANGEROUS_DRIVING = "DANGEROUS_DRIVING"


class BehaviorFlagStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class CVDetection(Base):
    __tablename__ = "cv_detections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, primary_key=True, default=datetime.utcnow, nullable=False)
    camera_id = Column(String(64), nullable=False, index=True)
    track_id = Column(String(64), nullable=True, index=True)
    vehicle_class = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    bbox = Column(JSON, nullable=False)
    pcu = Column(Float, nullable=False)
    frame_ref = Column(String(256), nullable=True)


class BehaviorFlag(Base):
    __tablename__ = "behavior_flags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flag_type = Column(Enum(BehaviorFlagType), nullable=False, index=True)
    camera_id = Column(String(64), nullable=False, index=True)
    track_id = Column(String(64), nullable=False)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    evidence = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=False)
    status = Column(Enum(BehaviorFlagStatus), default=BehaviorFlagStatus.UNVERIFIED, nullable=False, index=True)
    note = Column(
        String(256),
        default="Behaviour flagged for review. Not a confirmed violation.",
        nullable=False,
    )
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    frame_ref = Column(String(256), nullable=True)
    source = Column(String(32), default="vision", nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("status", BehaviorFlagStatus.UNVERIFIED)
        kwargs.setdefault("note", "Behaviour flagged for review. Not a confirmed violation.")
        kwargs.setdefault("source", "vision")
        # Pre-bind resolved_by before super().__init__ evaluates status validator
        if "resolved_by" in kwargs:
            self.resolved_by = kwargs.pop("resolved_by")
        super().__init__(**kwargs)

    @validates("status")
    def validate_status_transition(self, key, value):
        # Human gate: CONFIRMED must not be set without an operator action
        if value in (BehaviorFlagStatus.CONFIRMED, "CONFIRMED") and not getattr(self, "resolved_by", None):
            raise ValueError(
                "BehaviorFlag status cannot be set to CONFIRMED without an operator action (resolved_by is required)."
            )
        return value

    @validates("resolved_by")
    def validate_resolved_by(self, key, value):
        # Prevent clearing resolved_by once confirmed
        if value is None and getattr(self, "status", None) in (BehaviorFlagStatus.CONFIRMED, "CONFIRMED"):
            raise ValueError("Cannot remove resolved_by operator from a CONFIRMED BehaviorFlag.")
        return value


class NoParkingZone(Base):
    __tablename__ = "no_parking_zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    camera_id = Column(String(64), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    polygon = Column(JSON, nullable=False)
    active_start_time = Column(String(16), nullable=True)
    active_end_time = Column(String(16), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
