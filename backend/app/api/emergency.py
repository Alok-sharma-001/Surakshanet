from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid

class EmergencyActivate(BaseModel):
    priority: str
    vehicle_type: str
    route_junction_ids: List[str]

# Mock dependencies
async def get_db():
    yield None

class MockAuth:
    def __call__(self, required_role=None):
        return None

auth = MockAuth()

router = APIRouter(prefix="/emergency", tags=["emergency"])

try:
    from ml.emergency.green_wave import GreenWaveController
except (ImportError, ValueError):
    class GreenWaveController:
        def __init__(self): self.events = {}
        def activate(self, event_id, priority, vehicle_type, route_junction_ids):
            self.events[event_id] = {"status": "ACTIVE", "priority": priority, "vehicle_type": vehicle_type, "route": route_junction_ids}
            return {"status": "success", "event_id": event_id, "active": True}
        def deactivate(self, event_id):
            if event_id in self.events:
                self.events[event_id]["status"] = "COMPLETED"
                return {"status": "success", "event_id": event_id, "active": False}
            return {"status": "error", "message": "Event not found"}
        def get_status(self, event_id=None):
            if event_id: return self.events.get(event_id)
            return list(self.events.values())

green_wave_ctrl = GreenWaveController()

@router.post("/activate")
async def activate_emergency(
    data: EmergencyActivate,
    user=Depends(auth(required_role="operator"))
):
    """Activate emergency green-wave."""
    event_id = str(uuid.uuid4())
    result = green_wave_ctrl.activate(
        event_id=event_id,
        priority=data.priority,
        vehicle_type=data.vehicle_type,
        route_junction_ids=data.route_junction_ids
    )
    # Broadcast via websocket would go here
    return result

@router.post("/deactivate/{event_id}")
async def deactivate_emergency(
    event_id: str,
    user=Depends(auth(required_role="operator"))
):
    """Deactivate green-wave."""
    result = green_wave_ctrl.deactivate(event_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result

@router.get("/status")
async def get_all_status():
    """Get all active emergency events."""
    return green_wave_ctrl.get_status()

@router.get("/status/{event_id}")
async def get_event_status(event_id: str):
    """Get specific event status."""
    status = green_wave_ctrl.get_status(event_id)
    if not status:
        raise HTTPException(status_code=404, detail="Event not found")
    return status

@router.get("/history")
async def get_history(limit: int = 50, offset: int = 0):
    """Get past emergency events."""
    # Mock history from DB
    return {"events": [], "total": 0}
