import uuid
from datetime import datetime
from sqlalchemy import Column, Float, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

class TrafficReading(Base):
    __tablename__ = "traffic_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    sensor_id = Column(UUID(as_uuid=True), ForeignKey("traffic_sensors.id"), nullable=False)
    junction_id = Column(UUID(as_uuid=True), ForeignKey("junctions.id"), nullable=False)
    vehicle_count = Column(Float, nullable=False)
    pcu_value = Column(Float, nullable=False)
    avg_speed = Column(Float, nullable=True)
    queue_length = Column(Float, nullable=True)
    vehicle_breakdown = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
