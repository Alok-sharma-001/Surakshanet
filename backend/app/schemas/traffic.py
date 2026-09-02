from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class JunctionCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    num_approaches: int = 4
    geometry: Optional[Dict[str, Any]] = None

class JunctionResponse(BaseModel):
    id: UUID
    name: str
    latitude: float
    longitude: float
    num_approaches: int
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class JunctionUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_active: Optional[bool] = None

class SensorCreate(BaseModel):
    junction_id: UUID
    sensor_type: str
    approach_direction: str

class SensorResponse(BaseModel):
    id: UUID
    junction_id: UUID
    sensor_type: str
    approach_direction: str
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class TrafficReadingCreate(BaseModel):
    sensor_id: UUID
    junction_id: UUID
    vehicle_count: float
    pcu_value: float
    avg_speed: Optional[float] = None
    queue_length: Optional[float] = None
    vehicle_breakdown: Optional[Dict[str, Any]] = None

class TrafficReadingResponse(BaseModel):
    id: UUID
    timestamp: datetime
    sensor_id: UUID
    junction_id: UUID
    vehicle_count: float
    pcu_value: float
    avg_speed: Optional[float]
    queue_length: Optional[float]
    vehicle_breakdown: Optional[Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)

class TrafficReadingQuery(BaseModel):
    junction_id: Optional[UUID] = None
    sensor_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    limit: int = 100
    offset: int = 0
