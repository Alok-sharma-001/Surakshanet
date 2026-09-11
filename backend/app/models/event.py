import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class EventType(str, enum.Enum):
    RALLY = "RALLY"
    PROCESSION = "PROCESSION"
    FESTIVAL = "FESTIVAL"
    VIP_MOVEMENT = "VIP_MOVEMENT"
    MARATHON = "MARATHON"
    CONCERT = "CONCERT"
    DEMONSTRATION = "DEMONSTRATION"
    GOVERNMENT = "GOVERNMENT"
    OTHER = "OTHER"


class EventIntensity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EventStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PREDICTED = "PREDICTED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class Event(Base):
    __tablename__ = "events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    event_type = Column(Enum(EventType), nullable=False, default=EventType.OTHER)
    starts_at = Column(DateTime, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    expected_crowd = Column(Integer, nullable=True)
    affected_links = Column(JSON, nullable=True)  # List of SUMO edge IDs
    closure_links = Column(JSON, nullable=True)   # Subset of edges fully closed
    intensity = Column(Enum(EventIntensity), nullable=False, default=EventIntensity.MEDIUM)
    status = Column(Enum(EventStatus), nullable=False, default=EventStatus.DRAFT)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)


class EventPrediction(Base):
    __tablename__ = "event_predictions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    seed = Column(Integer, nullable=False)
    baseline_metrics = Column(JSON, nullable=True)
    event_metrics = Column(JSON, nullable=True)
    link_deltas = Column(JSON, nullable=True)
    severity_summary = Column(JSON, nullable=True)
    alternatives = Column(JSON, nullable=True)
    demand_injection = Column(JSON, nullable=True)  # {assumed_vehicle_trips, injected_vehicle_trips, demand_capped}
    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    source = Column(String(32), default="sumo", nullable=False)
