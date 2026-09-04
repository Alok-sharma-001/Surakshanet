import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
import redis.asyncio as aioredis

from app.database import get_db
from app.config import get_settings
from app.models.alert import (
    EmergencyEvent,
    EmergencyPriority,
    EmergencyVehicleType,
    EmergencyStatus
)
from app.models.user import User
from app.services.auth_service import get_current_user
from ml.emergency.green_wave import GreenWaveController

settings = get_settings()
router = APIRouter(prefix="/emergency", tags=["emergency"])

# Singleton controller managing active signal pre-emptions in memory
green_wave_ctrl = GreenWaveController(lookahead=4, green_hold_s=35)

class EmergencyActivateRequest(BaseModel):
    priority: str = "CRITICAL"
    vehicle_type: str = "AMBULANCE"
    route_junction_ids: Optional[List[str]] = None
    corridor: Optional[List[str]] = None
    vehicle_id: Optional[str] = None
    destination: Optional[str] = None

    def get_route(self) -> List[str]:
        return self.route_junction_ids or self.corridor or ["DEL-CP-01", "DEL-ITO-02", "DEL-ASH-04"]

@router.post("/activate")
async def activate_emergency(
    data: EmergencyActivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Activate an emergency green wave along a designated junction route."""
    event_uuid = uuid.uuid4()
    event_id = str(event_uuid)
    route = data.get_route()

    # 1. Activate green wave algorithm
    result = green_wave_ctrl.activate(
        event_id=event_id,
        priority=data.priority,
        vehicle_type=data.vehicle_type,
        route_junction_ids=route
    )

    # 2. Persist event to database
    try:
        priority_enum = EmergencyPriority[data.priority.upper()]
    except KeyError:
        priority_enum = EmergencyPriority.CRITICAL

    try:
        vehicle_enum = EmergencyVehicleType[data.vehicle_type.upper()]
    except KeyError:
        vehicle_enum = EmergencyVehicleType.AMBULANCE

    event = EmergencyEvent(
        id=event_uuid,
        priority=priority_enum,
        vehicle_type=vehicle_enum,
        route=route,
        status=EmergencyStatus.ACTIVE,
        activated_by=current_user.id if current_user else None,
        started_at=datetime.utcnow()
    )
    db.add(event)
    await db.commit()

    # 3. Broadcast to Redis for live WebSocket push
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        pub_payload = {
            "type": "EMERGENCY_ACTIVATED",
            "event_id": event_id,
            "priority": data.priority,
            "vehicle_type": data.vehicle_type,
            "route": route,
            "preempted_signals": len(route)
        }
        await redis.publish("emergency_events", json.dumps(pub_payload))
        await redis.aclose()
    except Exception:
        pass

    return {
        "status": "success",
        "event_id": event_id,
        "priority": data.priority,
        "route": route,
        "preempted_signals": len(route),
        "active": True,
        "details": result.get("event")
    }

@router.post("/deactivate/{event_id}")
async def deactivate_emergency(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """Deactivate an active green wave and restore default signal cycles."""
    # 1. Update database record
    try:
        event_uuid = uuid.UUID(event_id)
        stmt = select(EmergencyEvent).where(EmergencyEvent.id == event_uuid)
        res = await db.execute(stmt)
        event = res.scalar_one_or_none()
        if event:
            event.status = EmergencyStatus.COMPLETED
            event.ended_at = datetime.utcnow()
            await db.commit()
    except Exception:
        pass

    # 2. Deactivate in in-memory controller
    green_wave_ctrl.deactivate(event_id)

    # 3. Broadcast to Redis
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        pub_payload = {
            "type": "EMERGENCY_DEACTIVATED",
            "event_id": event_id,
            "status": "COMPLETED"
        }
        await redis.publish("emergency_events", json.dumps(pub_payload))
        await redis.aclose()
    except Exception:
        pass

    return {
        "status": "deactivated",
        "event_id": event_id,
        "active": False
    }

@router.get("/status")
@router.get("/active")
async def get_active_emergencies(db: AsyncSession = Depends(get_db)):
    """Get all currently active emergency corridors from DB."""
    stmt = (
        select(EmergencyEvent)
        .where(
            EmergencyEvent.status == EmergencyStatus.ACTIVE,
            EmergencyEvent.route.isnot(None)
        )
        .order_by(desc(EmergencyEvent.started_at))
    )
    res = await db.execute(stmt)
    active_db = res.scalars().all()

    active_events = []
    for e in active_db:
        if not e.route or e.route == "null":
            continue
        active_events.append({
            "id": str(e.id),
            "priority": e.priority.value if hasattr(e.priority, 'value') else str(e.priority),
            "vehicle_type": e.vehicle_type.value if hasattr(e.vehicle_type, 'value') else str(e.vehicle_type),
            "route": e.route,
            "current_index": 0,
            "active_junctions": e.route[:4] if isinstance(e.route, list) else [],
            "timestamp": e.started_at.timestamp() if e.started_at else datetime.utcnow().timestamp()
        })

    return {"active_events": active_events}

@router.get("/status/{event_id}")
async def get_emergency_status(event_id: str):
    """Get status of a specific emergency corridor."""
    status = green_wave_ctrl.get_status(event_id)
    if not status:
        raise HTTPException(status_code=404, detail="Active emergency event not found")
    return status

@router.get("/history")
async def get_emergency_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Query historical emergency events from database."""
    stmt = (
        select(EmergencyEvent)
        .order_by(desc(EmergencyEvent.started_at))
        .offset(offset)
        .limit(limit)
    )
    res = await db.execute(stmt)
    records = res.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "priority": e.priority.value if hasattr(e.priority, 'value') else str(e.priority),
                "vehicle_type": e.vehicle_type.value if hasattr(e.vehicle_type, 'value') else str(e.vehicle_type),
                "route": e.route,
                "status": e.status.value if hasattr(e.status, 'value') else str(e.status),
                "started_at": e.started_at.isoformat(),
                "ended_at": e.ended_at.isoformat() if e.ended_at else None
            }
            for e in records
        ],
        "total": len(records)
    }
