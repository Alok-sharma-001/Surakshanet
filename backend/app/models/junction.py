import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from geoalchemy2 import Geometry
import geoalchemy2.admin.dialects.sqlite as g_sqlite

# Graceful SQLite fallback: catch RecoverGeometryColumn if spatialite is absent in unit tests
orig_after_create = g_sqlite.after_create
def safe_sqlite_after_create(table, bind, **kw):
    try:
        orig_after_create(table, bind, **kw)
    except Exception as e:
        if "RecoverGeometryColumn" in str(e):
            pass
        else:
            raise
g_sqlite.after_create = safe_sqlite_after_create

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
    location = Column(Geometry(geometry_type="POINT", srid=4326, spatial_index=True), nullable=True)
    num_approaches = Column(Integer, default=4, nullable=False)
    geometry = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sensors = relationship("TrafficSensor", back_populates="junction", cascade="all, delete-orphan")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.location is None and self.latitude is not None and self.longitude is not None:
            self.location = f"SRID=4326;POINT({self.longitude} {self.latitude})"

    @validates("latitude", "longitude")
    def _sync_location(self, key, value):
        if key == "latitude":
            lat = value
            lon = self.longitude
        else:
            lat = self.latitude
            lon = value
        if lat is not None and lon is not None:
            self.location = f"SRID=4326;POINT({lon} {lat})"
        return value

class TrafficSensor(Base):
    __tablename__ = "traffic_sensors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    junction_id = Column(UUID(as_uuid=True), ForeignKey("junctions.id", ondelete="CASCADE"), nullable=False)
    sensor_type = Column(Enum(SensorType), nullable=False)
    approach_direction = Column(Enum(ApproachDirection), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    junction = relationship("Junction", back_populates="sensors")
