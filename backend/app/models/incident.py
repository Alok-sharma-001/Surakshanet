import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime, Enum, ForeignKey, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates, relationship, Session
from app.database import Base


class IncidentType(str, enum.Enum):
    # SN-083: The only incident_type value is POSSIBLE_INCIDENT.
    # There is deliberately no ACCIDENT value — the schema itself prevents the overclaim.
    POSSIBLE_INCIDENT = "POSSIBLE_INCIDENT"


class IncidentStatus(str, enum.Enum):
    # SN-090..SN-094: Response state machine statuses
    DETECTED = "DETECTED"
    UNVERIFIED = "UNVERIFIED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    RESPONDING = "RESPONDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentIndicatorType(str, enum.Enum):
    # SN-086..SN-088: Five measured indicators
    SPEED_COLLAPSE = "SPEED_COLLAPSE"
    STATIONARY_VEHICLE = "STATIONARY_VEHICLE"
    OCCUPANCY_SPIKE = "OCCUPANCY_SPIKE"
    FLOW_DROP = "FLOW_DROP"
    QUEUE_ANOMALY = "QUEUE_ANOMALY"


class Incident(Base):
    """SN-083: Incident data model representing an automated anomaly detection event.

    Human gate 1: Confirmation by operator/admin is required before downstream automation.
    Human gate 2: Warning publication is restricted to ADMIN and requires CONFIRMED status.
    """
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_type = Column(Enum(IncidentType), default=IncidentType.POSSIBLE_INCIDENT, nullable=False)
    status = Column(Enum(IncidentStatus), default=IncidentStatus.UNVERIFIED, nullable=False, index=True)
    link_id = Column(String(64), nullable=False, index=True)
    junction_id = Column(String(64), nullable=True, index=True)
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    confidence = Column(Float, nullable=False)  # Anomaly score between 0.0 and 1.0
    indicators_fired = Column(Integer, default=1, nullable=False)
    indicators_total = Column(Integer, default=5, nullable=False)
    evidence_ref = Column(String(256), nullable=True)
    confirmed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_at = Column(DateTime, nullable=True)
    resolution = Column(String(256), nullable=True)
    warning_published_at = Column(DateTime, nullable=True)
    warning_published_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    source = Column(String(32), default="sumo", nullable=False)
    note = Column(
        String(256),
        default="Possible incident. Unverified — operator review required.",
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    indicators = relationship(
        "IncidentIndicator",
        back_populates="incident",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("incident_type", IncidentType.POSSIBLE_INCIDENT)
        kwargs.setdefault("status", IncidentStatus.UNVERIFIED)
        kwargs.setdefault("note", "Possible incident. Unverified — operator review required.")
        kwargs.setdefault("source", "sumo")
        kwargs.setdefault("indicators_fired", 1)
        kwargs.setdefault("indicators_total", 5)
        kwargs.setdefault("detected_at", datetime.utcnow())

        # Pre-bind operator actions before super().__init__ evaluates validators
        if "confirmed_by" in kwargs:
            self.confirmed_by = kwargs.pop("confirmed_by")
        if "warning_published_by" in kwargs:
            self.warning_published_by = kwargs.pop("warning_published_by")
        super().__init__(**kwargs)

    @validates("status")
    def validate_status(self, key, value):
        # Human Gate 1: Setting CONFIRMED requires an operator action
        if value in (IncidentStatus.CONFIRMED, "CONFIRMED") and not getattr(self, "confirmed_by", None):
            raise ValueError(
                "Incident status cannot be set to CONFIRMED without an operator action (confirmed_by is required)."
            )
        return value

    @validates("confirmed_by")
    def validate_confirmed_by(self, key, value):
        # Prevent clearing confirmed_by once confirmed unless auto_cleared
        if value is None and getattr(self, "status", None) in (
            IncidentStatus.CONFIRMED,
            "CONFIRMED",
            IncidentStatus.RESPONDING,
            "RESPONDING",
        ):
            if getattr(self, "resolution", None) != "auto_cleared":
                raise ValueError("Cannot remove confirmed_by operator from a CONFIRMED Incident.")
        return value

    @validates("warning_published_at")
    def validate_warning_published_at(self, key, value):
        # Human Gate 2: Cannot publish warning on unconfirmed incident
        if value is not None:
            curr_status = getattr(self, "status", None)
            if curr_status not in (
                IncidentStatus.CONFIRMED,
                "CONFIRMED",
                IncidentStatus.RESPONDING,
                "RESPONDING",
            ):
                raise ValueError("Incident must be CONFIRMED before a public warning can be published.")
        return value


class IncidentIndicator(Base):
    """SN-084: Measured indicator row tied to an incident."""
    __tablename__ = "incident_indicators"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indicator = Column(Enum(IncidentIndicatorType), nullable=False, index=True)
    measured_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    fired_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    incident = relationship("Incident", back_populates="indicators")

    def __init__(self, **kwargs):
        kwargs.setdefault("fired_at", datetime.utcnow())
        super().__init__(**kwargs)


@event.listens_for(Session, "before_flush")
def validate_incident_has_indicators(session, flush_context, instances):
    """SN-084: Integrity rule: An incident cannot exist without a measured indicator.

    Reject inserting an incident with zero indicator rows at write time.
    """
    for obj in session.new:
        if isinstance(obj, Incident):
            has_indicators = False
            if obj.indicators and len(obj.indicators) > 0:
                has_indicators = True
            else:
                for other in session.new:
                    if isinstance(other, IncidentIndicator):
                        if other.incident_id == obj.id or other.incident is obj:
                            has_indicators = True
                            break
            if not has_indicators:
                raise ValueError(
                    "An incident cannot exist without at least one measured indicator (zero indicator rows rejected)."
                )
