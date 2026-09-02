from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class TelemetryData(BaseModel):
    junction_id: str
    timestamp: float
    north_pcu: float
    east_pcu: float
    south_pcu: float
    west_pcu: float
    avg_speed: float
    queue_length: float
    phase: str
    vehicle_counts: Optional[Dict[str, int]] = None

class JunctionState(BaseModel):
    junction_id: str
    timestamp: float
    approaches: Dict[str, Dict[str, float]]
    current_phase: str
    phase_elapsed: float
    mode: str = 'MARL'

class SignalCommand(BaseModel):
    junction_id: str
    action: str
    phase: Optional[str] = None
    duration: Optional[float] = None

class AlertPayload(BaseModel):
    alert_id: str
    junction_id: Optional[str] = None
    alert_type: str
    severity: str
    message: str
    timestamp: float

class EmergencyPayload(BaseModel):
    event_id: str
    priority: str
    vehicle_type: str
    route: List[str]
    status: str
    current_junction: Optional[str] = None

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float

class RouteResponse(BaseModel):
    routes: List[Dict]
