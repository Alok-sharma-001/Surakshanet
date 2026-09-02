import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class SensorType(str, enum.Enum):
    CAMERA = "CAMERA"
    INDUCTION = "INDUCTION"
    ACOUSTIC = "ACOUSTIC"
    GPS = "GPS"

class ApproachDirection(str, enum.Enum):
    N = "N"
    E = "E"
    S = "S"
    W = "W"

class Junction(Base):
    __tablename__ = "junctions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    num_approaches = Column(Integer, default=4, nullable=False)
    geometry = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sensors = relationship("TrafficSensor", back_populates="junction")

class TrafficSensor(Base):
    __tablename__ = "traffic_sensors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    junction_id = Column(UUID(as_uuid=True), ForeignKey("junctions.id"), nullable=False)
    sensor_type = Column(Enum(SensorType), nullable=False)
    approach_direction = Column(Enum(ApproachDirection), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    junction = relationship("Junction", back_populates="sensors")
