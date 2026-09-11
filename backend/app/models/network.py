import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class NetworkLink(Base):
    __tablename__ = "network_links"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_junction = Column(String(64), nullable=False)
    to_junction = Column(String(64), nullable=False)
    sumo_edge_id = Column(String(64), nullable=False)
    length_m = Column(Float, nullable=False)
    lanes = Column(Integer, default=2, nullable=False)
    free_flow_speed_kmh = Column(Float, default=50.0, nullable=False)
    capacity_pcu_h = Column(Float, default=2000.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
