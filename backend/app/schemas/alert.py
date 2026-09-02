from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class AlertCreate(BaseModel):
    junction_id: Optional[UUID] = None
    alert_type: str
    severity: str
    message: str

class AlertResponse(BaseModel):
    id: UUID
    junction_id: Optional[UUID]
    alert_type: str
    severity: str
    message: str
    is_acknowledged: bool
    created_at: datetime
    acknowledged_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)

class EmergencyActivate(BaseModel):
    priority: str
    vehicle_type: str
    route: List[UUID]

class EmergencyResponse(BaseModel):
    id: UUID
    priority: str
    vehicle_type: str
    route: List[UUID]
    status: str
    activated_by: Optional[UUID]
    started_at: datetime
    ended_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)
