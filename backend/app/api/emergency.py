import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.services.auth_service import get_optional_current_user
from app.services.routing_service import routing_service
from ml.emergency.green_wave import green_wave_ctrl
from shared.constants import DataSource, REDIS_CHANNELS

settings = get_settings()
router = APIRouter(prefix="/emergency", tags=["emergency"])


class LocationPoint(BaseModel):
    lat: float
    lon: Optional[float] = None
    lng: Optional[float] = None
    name: Optional[str] = None

    def get_lon(self) -> float:
        return self.lon if self.lon is not None else (self.lng if self.lng is not None else 0.0)


class EmergencyActivateRequest(BaseModel):
    priority: str = "CRITICAL"
    vehicle_type: str = "AMBULANCE"
    vehicle_id: Optional[str] = None
    origin: Optional[LocationPoint] = None
    destination: Optional[LocationPoint] = None
    route_junction_ids: Optional[List[str]] = None
    corridor: Optional[List[str]] = None

    def resolve_route(self) -> List[str]:
        """Resolves the route from explicit list or by computing A* over live weights (SN-049).

        Never defaults to an invented corridor, origin, or destination. A request
        without an explicit route needs BOTH origin and destination — A* cannot
        compute a path from a fabricated starting point — or it is 422.
        """
        route = self.route_junction_ids or self.corridor
        if route and len(route) > 0:
            return route

        if not self.destination or not self.origin:
            raise HTTPException(
                status_code=422,
                detail="route_junction_ids/corridor, or both origin and destination, are "
                       "required; an emergency route, origin, or destination is never assumed",
            )

        # Compute route via A* using emergency profile (0.7 travel_time + 0.3 distance, no congestion penalty)
        origin_coords = (self.origin.lat, self.origin.get_lon())
        dest_coords = (self.destination.lat, self.destination.get_lon())

        route_result = routing_service.find_route(origin_coords, dest_coords, profile="emergency")
        computed_path = route_result.get("path", [])

        if not computed_path:
            raise HTTPException(
                status_code=422,
                detail="Could not calculate valid path to specified destination.",
            )

        return computed_path


@router.post("/activate", status_code=status.HTTP_201_CREATED)
async def activate_emergency(
    data: EmergencyActivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Activate an emergency green wave along a designated junction route (SN-039..SN-049)."""
    event_uuid = uuid.uuid4()
    event_id = str(event_uuid)
    route = data.resolve_route()

    vehicle_id = data.vehicle_id or f"AMB-{str(event_uuid)[:4].upper()}"
    origin_dict = (
        {"lat": data.origin.lat, "lon": data.origin.get_lon()}
        if data.origin
        else None
    )
    dest_dict = (
        {"lat": data.destination.lat, "lon": data.destination.get_lon(), "name": data.destination.name}
        if data.destination
        else None
    )

    # 1. Activate rolling green wave controller, seeded with real per-link
    #    lengths/speeds from the live routing graph rather than an assumed constant.
    result = green_wave_ctrl.activate(
        event_id=event_id,
        priority=data.priority,
        vehicle_type=data.vehicle_type,
        route_junction_ids=route,
        origin=origin_dict,
        destination=dest_dict,
        vehicle_id=vehicle_id,
        edge_lengths_m=routing_service.get_edge_lengths_m(route),
        link_speeds=routing_service.get_edge_speeds_kmh(route),
    )

    # 2. Persist event to database with full corridor metadata
    try:
        priority_enum = EmergencyPriority[data.priority.upper()]
    except KeyError:
        priority_enum = EmergencyPriority.CRITICAL

    try:
        vehicle_enum = EmergencyVehicleType[data.vehicle_type.upper()]
    except KeyError:
        vehicle_enum = EmergencyVehicleType.AMBULANCE

    now = datetime.utcnow()
    event = EmergencyEvent(
        id=event_uuid,
        vehicle_id=vehicle_id,
        priority=priority_enum,
        vehicle_type=vehicle_enum,
        origin_lat=origin_dict["lat"] if origin_dict else None,
        origin_lon=origin_dict["lon"] if origin_dict else None,
        destination_lat=dest_dict["lat"] if dest_dict else None,
        destination_lon=dest_dict["lon"] if dest_dict else None,
        destination_name=dest_dict.get("name") if dest_dict else None,
        route=route,
        route_etas=result.get("route_etas"),
        clearance_time_s=result.get("clearance_time_s"),
        status=EmergencyStatus.ACTIVE,
        activated_by=current_user.id if current_user else None,
        started_at=now,
    )
    db.add(event)
    await db.commit()

    # 3. Broadcast to Redis for live WebSocket push
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        pub_payload = {
            "type": "EMERGENCY_ACTIVATED",
            "event_id": event_id,
            "vehicle_id": vehicle_id,
            "priority": data.priority,
            "vehicle_type": data.vehicle_type,
            "route": route,
            "route_etas": result.get("route_etas"),
            "clearance_time_s": result.get("clearance_time_s"),
            "activation_policy": "rolling",
            "preempted_signals": len(route),
            "source": DataSource.SUMO.value,
        }
        await redis.publish(REDIS_CHANNELS["emergency"], json.dumps(pub_payload))
        await redis.aclose()
    except Exception:
        pass

    return {
        "status": "success",
        "event_id": event_id,
        "vehicle_id": vehicle_id,
        "priority": data.priority,
        "route": route,
        "route_etas": result.get("route_etas"),
        "clearance_time_s": result.get("clearance_time_s"),
        "activation_policy": "rolling",
        "source": DataSource.SUMO.value,
        "preempted_signals": len(route),
        "active": True,
    }


def _corridor_status_from_db_event(event: EmergencyEvent) -> Dict[str, Any]:
    """Builds a corridor-status response from the DB row.

    The bridge process — the only process with a live TraCI connection — is
    the sole writer of `route_etas`/`captured_programs`/`restored_at` once a
    corridor is running, so the DB row (not the API process's own in-memory
    controller, which never sees the bridge's progress) is the source of
    truth for live status.
    """
    route_etas = event.route_etas or []
    total_j = len(route_etas)
    curr_idx = next(
        (i for i, e in enumerate(route_etas) if e.get("state") not in ("restored", "restore_failed", "passed_unmanaged")),
        max(0, total_j - 1),
    )
    next_junction = route_etas[curr_idx]["junction_id"] if total_j > 0 else None

    return {
        "event_id": str(event.id),
        "status": event.status.value if hasattr(event.status, "value") else str(event.status),
        "vehicle_id": event.vehicle_id,
        "next_junction": next_junction,
        "clearance_time_s": event.clearance_time_s or 0.0,
        "junctions": route_etas,
        "cross_street": {
            "max_red_s": event.cross_street_max_red_s or 0.0,
        },
        "restored_at": event.restored_at.isoformat() if event.restored_at else None,
        "source": DataSource.SUMO.value,
    }


@router.post("/deactivate/{event_id}")
async def deactivate_emergency(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Requests early deactivation of an active corridor (SN-045/SN-048).

    This only signals intent. It does NOT itself mark the event COMPLETED or
    set restored_at: only the bridge process — which holds the live TraCI
    connection and can actually restore and verify each junction's captured
    program — may make that claim, once it has genuinely done so. Claiming
    completion here would be exactly the kind of unverified success this
    endpoint exists to avoid.
    """
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Emergency event not found")

    stmt = select(EmergencyEvent).where(EmergencyEvent.id == event_uuid)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Emergency event not found")
    if event.status != EmergencyStatus.ACTIVE:
        raise HTTPException(status_code=409, detail=f"Emergency event is already {event.status}")

    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        pub_payload = {
            "type": "EMERGENCY_DEACTIVATED",
            "event_id": event_id,
        }
        await redis.publish(REDIS_CHANNELS["emergency"], json.dumps(pub_payload))
        await redis.aclose()
    except Exception:
        pass

    return {
        "status": "deactivation_requested",
        "event_id": event_id,
        "note": "Corridor will be marked COMPLETED once the simulation bridge verifies every junction is restored.",
    }


@router.get("/{event_id}/corridor")
async def get_emergency_corridor(event_id: str, db: AsyncSession = Depends(get_db)):
    """Get live rolling corridor status with per-junction states and countdown (SN-043)."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Active or recent emergency event not found")
    stmt = select(EmergencyEvent).where(EmergencyEvent.id == event_uuid)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Active or recent emergency event not found")
    return _corridor_status_from_db_event(event)


@router.get("/{event_id}/eta")
async def get_emergency_eta(event_id: str, db: AsyncSession = Depends(get_db)):
    """Get per-junction ETA sequence for active corridor (SN-042)."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Emergency event not found")
    stmt = select(EmergencyEvent).where(EmergencyEvent.id == event_uuid)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Emergency event not found")
    return {
        "event_id": event_id,
        "junctions": event.route_etas or [],
        "clearance_time_s": event.clearance_time_s or 0.0,
        "source": DataSource.SUMO.value,
    }


@router.get("/{event_id}/recovery")
async def get_emergency_recovery(event_id: str, db: AsyncSession = Depends(get_db)):
    """Get measured cross-traffic delay recovery curve; returns 503 while ACTIVE (SN-048).

    recovery_s is null until the bridge has actually measured it from real
    samples — never a placeholder number.
    """
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Emergency event not found")
    stmt = select(EmergencyEvent).where(EmergencyEvent.id == event_uuid)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Emergency event not found")
    if event.status == EmergencyStatus.ACTIVE:
        raise HTTPException(
            status_code=503,
            detail="Corridor is still ACTIVE. Recovery delay can only be measured after corridor deactivation.",
        )

    rec = event.recovery_series or {}
    return {
        "event_id": event_id,
        "recovery_s": event.recovery_s,
        "resolved": rec.get("resolved", False),
        "baseline_available": rec.get("baseline_available", False),
        "cross_street_baseline_delay_s": rec.get("baseline_delay_s"),
        "cross_street_peak_delay_s": rec.get("peak_delay_s"),
        "series": rec.get("series", []),
        "source": DataSource.SUMO.value,
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
        route_etas = e.route_etas or []
        active_events.append({
            "id": str(e.id),
            "vehicle_id": e.vehicle_id or f"AMB-{str(e.id)[:4].upper()}",
            "priority": e.priority.value if hasattr(e.priority, 'value') else str(e.priority),
            "vehicle_type": e.vehicle_type.value if hasattr(e.vehicle_type, 'value') else str(e.vehicle_type),
            "route": e.route,
            "route_etas": route_etas,
            "clearance_time_s": e.clearance_time_s or 0.0,
            "active_junctions": [j["junction_id"] for j in route_etas if j.get("state") == "preempted"],
            "timestamp": e.started_at.timestamp() if e.started_at else datetime.utcnow().timestamp(),
            "source": DataSource.SUMO.value,
        })

    return {"active_events": active_events}


@router.get("/status/{event_id}")
async def get_emergency_status(event_id: str, db: AsyncSession = Depends(get_db)):
    """Get status of a specific emergency corridor."""
    try:
        event_uuid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Active emergency event not found")
    stmt = select(EmergencyEvent).where(EmergencyEvent.id == event_uuid)
    res = await db.execute(stmt)
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Active emergency event not found")
    return _corridor_status_from_db_event(event)


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
                "vehicle_id": e.vehicle_id,
                "priority": e.priority.value if hasattr(e.priority, 'value') else str(e.priority),
                "vehicle_type": e.vehicle_type.value if hasattr(e.vehicle_type, 'value') else str(e.vehicle_type),
                "route": e.route,
                "route_etas": e.route_etas,
                "status": e.status.value if hasattr(e.status, 'value') else str(e.status),
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "restored_at": e.restored_at.isoformat() if e.restored_at else None,
                "ended_at": e.ended_at.isoformat() if e.ended_at else None,
                "clearance_time_s": e.clearance_time_s,
                "recovery_s": e.recovery_s,
                "source": DataSource.SUMO.value,
            }
            for e in records
        ],
        "total": len(records)
    }
