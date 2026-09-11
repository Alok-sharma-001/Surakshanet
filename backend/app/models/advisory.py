import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Enum, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import validates
from app.database import Base


class AdvisoryOriginType(str, enum.Enum):
    EVENT = "EVENT"
    INCIDENT = "INCIDENT"
    EMERGENCY = "EMERGENCY"
    FORECAST = "FORECAST"


class AdvisorySeverity(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    SEVERE = "SEVERE"


class CitizenAdvisory(Base):
    __tablename__ = "citizen_advisories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    origin_type = Column(Enum(AdvisoryOriginType), nullable=False)
    origin_id = Column(UUID(as_uuid=True), nullable=True)
    headline = Column(String(120), nullable=False)
    corridor_text = Column(String(256), nullable=False)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    delay_min_low = Column(Integer, nullable=False)
    delay_min_high = Column(Integer, nullable=False)
    cause_text = Column(String(256), nullable=False)
    recommended_route_text = Column(String(256), nullable=False)
    recommended_departure_before = Column(DateTime, nullable=True)
    severity = Column(Enum(AdvisorySeverity), nullable=False)
    published_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    published_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    source = Column(String(32), default="sumo", nullable=False)

    @validates("published_by")
    def validate_published_by(self, key, value):
        if value is None:
            raise ValueError(
                "CitizenAdvisory requires non-null published_by (publication is always an audited human act)."
            )
        return value
