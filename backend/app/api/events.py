import uuid
import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.event import Event, EventType, EventIntensity, EventStatus
from app.models.advisory import AdvisoryOriginType
from app.models.user import User
from app.services.auth_service import require_role
from app.services.event_service import (
    translate_demand,
    is_prediction_running,
    get_latest_prediction,
    launch_prediction_task,
)
from app.services.advisory_service import build_advisory
from app.services.audit_service import write_audit

logger = logging.getLogger("surakshanet.api.events")
router = APIRouter(prefix="/events", tags=["Events"])


# Pydantic Schemas
class EventCreateRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=128)
    event_type: EventType = EventType.OTHER
    starts_at: datetime
    ends_at: datetime
    expected_crowd: Optional[int] = Field(default=0, ge=0)
    affected_links: Optional[List[str]] = Field(default_factory=list)
    closure_links: Optional[List[str]] = Field(default_factory=list)
    intensity: EventIntensity = EventIntensity.MEDIUM


class EventUpdateRequest(BaseModel):
    name: Optional[str] = None
    event_type: Optional[EventType] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    expected_crowd: Optional[int] = None
    affected_links: Optional[List[str]] = None
    closure_links: Optional[List[str]] = None
    intensity: Optional[EventIntensity] = None


class PredictRequest(BaseModel):
    seed: int = 42
    duration_s: int = 300


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """Creates a new event in DRAFT status. Requires OPERATOR or ADMIN role."""
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ends_at must be strictly after starts_at",
        )

    event_id = uuid.uuid4()
    event = Event(
        id=event_id,
        name=payload.name,
        event_type=payload.event_type,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        expected_crowd=payload.expected_crowd,
        affected_links=payload.affected_links or [],
        closure_links=payload.closure_links or [],
        intensity=payload.intensity,
        status=EventStatus.DRAFT,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)

    demand_info = translate_demand(event.expected_crowd or 0)
    return {
        "event": {
            "id": str(event.id),
            "name": event.name,
            "event_type": event.event_type.value,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat(),
            "expected_crowd": event.expected_crowd,
            "affected_links": event.affected_links,
            "closure_links": event.closure_links,
            "intensity": event.intensity.value,
            "status": event.status.value,
            "created_by": str(event.created_by) if event.created_by else None,
            "created_at": event.created_at.isoformat(),
        },
        "demand_translation": demand_info,
    }


@router.get("")
async def list_events(
    status_filter: Optional[EventStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER")),
):
    """Lists all events. Accessible to VIEWER, OPERATOR, EMERGENCY_SERVICES, and ADMIN."""
    stmt = select(Event)
    if status_filter:
        stmt = stmt.where(Event.status == status_filter)
    stmt = stmt.order_by(desc(Event.created_at))

    result = await db.execute(stmt)
    events = result.scalars().all()

    output = []
    for evt in events:
        output.append({
            "id": str(evt.id),
            "name": evt.name,
            "event_type": evt.event_type.value,
            "starts_at": evt.starts_at.isoformat(),
            "ends_at": evt.ends_at.isoformat(),
            "expected_crowd": evt.expected_crowd,
            "affected_links": evt.affected_links,
            "closure_links": evt.closure_links,
            "intensity": evt.intensity.value,
            "status": evt.status.value,
            "created_at": evt.created_at.isoformat(),
            "approved_at": evt.approved_at.isoformat() if evt.approved_at else None,
            "published_at": evt.published_at.isoformat() if evt.published_at else None,
            "demand_translation": translate_demand(evt.expected_crowd or 0),
        })
    return {"events": output, "count": len(output)}


@router.get("/{event_id}")
async def get_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER")),
):
    """Retrieves single event details, demand translation, and prediction status."""
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    pred = await get_latest_prediction(event_id, db)
    running = await is_prediction_running(str(event_id))

    return {
        "id": str(event.id),
        "name": event.name,
        "event_type": event.event_type.value,
        "starts_at": event.starts_at.isoformat(),
        "ends_at": event.ends_at.isoformat(),
        "expected_crowd": event.expected_crowd,
        "affected_links": event.affected_links,
        "closure_links": event.closure_links,
        "intensity": event.intensity.value,
        "status": event.status.value,
        "created_by": str(event.created_by) if event.created_by else None,
        "approved_by": str(event.approved_by) if event.approved_by else None,
        "created_at": event.created_at.isoformat(),
        "approved_at": event.approved_at.isoformat() if event.approved_at else None,
        "published_at": event.published_at.isoformat() if event.published_at else None,
        "demand_translation": translate_demand(event.expected_crowd or 0),
        "prediction_running": running,
        "has_prediction": pred is not None,
    }


@router.patch("/{event_id}")
async def update_event(
    event_id: uuid.UUID,
    payload: EventUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """Edits an event. Strictly allowed only while status is DRAFT (SN-053)."""
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status != EventStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot edit event with status {event.status.value}. Only DRAFT events can be modified.",
        )

    if payload.name is not None:
        event.name = payload.name
    if payload.event_type is not None:
        event.event_type = payload.event_type
    if payload.starts_at is not None:
        event.starts_at = payload.starts_at
    if payload.ends_at is not None:
        event.ends_at = payload.ends_at
    if payload.expected_crowd is not None:
        event.expected_crowd = payload.expected_crowd
    if payload.affected_links is not None:
        event.affected_links = payload.affected_links
    if payload.closure_links is not None:
        event.closure_links = payload.closure_links
    if payload.intensity is not None:
        event.intensity = payload.intensity

    if event.ends_at <= event.starts_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ends_at must be strictly after starts_at",
        )

    await db.commit()
    await db.refresh(event)

    return {
        "event": {
            "id": str(event.id),
            "name": event.name,
            "event_type": event.event_type.value,
            "status": event.status.value,
        },
        "demand_translation": translate_demand(event.expected_crowd or 0),
    }


@router.post("/{event_id}/predict", status_code=status.HTTP_202_ACCEPTED)
async def run_event_prediction(
    event_id: uuid.UUID,
    payload: Optional[PredictRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """
    Triggers dual-world what-if simulation (World A baseline vs World B event).
    Returns 202 while running (SN-055, SN-056).
    """
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    seed = payload.seed if payload else 42
    duration_s = payload.duration_s if payload else 300

    if await is_prediction_running(str(event_id)):
        return {
            "status": "running",
            "event_id": str(event_id),
            "seed": seed,
            "message": "Prediction simulation already running",
        }

    await launch_prediction_task(str(event_id), seed=seed, duration_s=duration_s)

    return {
        "status": "running",
        "event_id": str(event_id),
        "seed": seed,
        "message": "Dual-world simulation running at fixed seed",
    }


@router.get("/{event_id}/prediction")
async def get_event_prediction_endpoint(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER")),
):
    """
    Retrieves measured prediction results.
    Returns 202 while simulation is executing; 200 with measured deltas when complete.
    No severity is returned before both worlds complete (SN-056).
    """
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if await is_prediction_running(str(event_id)):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "event_id": str(event_id),
                "status": "running",
                "message": "Simulation in progress. Both worlds must complete before severity is computed.",
            },
        )

    pred = await get_latest_prediction(event_id, db)
    if not pred:
        raise HTTPException(
            status_code=404,
            detail="No prediction has been run for this event. Trigger POST /predict first.",
        )

    return {
        "event_id": str(pred.event_id),
        "seed": pred.seed,
        "status": "complete",
        "link_deltas": pred.link_deltas or [],
        "severity_summary": pred.severity_summary or {"LOW": 0, "MODERATE": 0, "SEVERE": 0},
        "alternatives": pred.alternatives or [],
        "source": pred.source or "sumo",
        "computed_at": pred.computed_at.isoformat() if pred.computed_at else None,
        "demand_injection": pred.demand_injection,
    }


@router.post("/{event_id}/approve")
async def approve_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """
    Approves an event. Requires ADMIN role and a completed prediction.
    Rejects with 409 if no completed prediction exists (SN-058).
    Writes an audit log entry.
    """
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    pred = await get_latest_prediction(event_id, db)
    if not pred or await is_prediction_running(str(event_id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot approve event without a completed prediction. Run prediction first.",
        )

    now = datetime.utcnow()
    event.status = EventStatus.APPROVED
    event.approved_by = current_user.id
    event.approved_at = now

    # Write audit log entry (SN-058)
    await write_audit(
        db=db,
        action="EVENT_APPROVE",
        actor_id=current_user.id,
        target_type="EVENT",
        target_id=event.id,
        input_payload={"event_id": str(event.id), "prediction_id": str(pred.id)},
        output_payload={"status": "APPROVED", "approved_at": now.isoformat()},
        source="manual",
    )

    await db.commit()
    await db.refresh(event)

    return {
        "id": str(event.id),
        "status": event.status.value,
        "approved_by": str(event.approved_by),
        "approved_at": event.approved_at.isoformat(),
    }


@router.post("/{event_id}/publish")
async def publish_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """
    Publishes an approved event, emitting exactly one citizen advisory (SN-058, SN-060, SN-068).
    Enforces the human gate: published_by is set to the acting admin.
    Writes an audit log entry.
    """
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status != EventStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Event must be APPROVED before publishing. Current status: {event.status.value}",
        )

    # Build and persist citizen advisory (human gate enforced)
    advisory = await build_advisory(
        db=db,
        origin_type=AdvisoryOriginType.EVENT,
        origin_id=event.id,
        user_id=current_user.id,
    )

    now = datetime.utcnow()
    event.status = EventStatus.PUBLISHED
    event.published_at = now

    # Write audit log entry (SN-058, SN-068)
    await write_audit(
        db=db,
        action="ADVISORY_PUBLISH",
        actor_id=current_user.id,
        target_type="ADVISORY",
        target_id=advisory.id,
        input_payload={"event_id": str(event.id), "advisory_id": str(advisory.id)},
        output_payload={"status": "PUBLISHED", "published_at": now.isoformat()},
        source="manual",
    )

    await db.commit()
    await db.refresh(event)

    return {
        "id": str(event.id),
        "status": event.status.value,
        "published_at": event.published_at.isoformat(),
        "advisory": {
            "id": str(advisory.id),
            "headline": advisory.headline,
            "corridor_text": advisory.corridor_text,
            "delay_min_low": advisory.delay_min_low,
            "delay_min_high": advisory.delay_min_high,
            "cause_text": advisory.cause_text,
            "recommended_route_text": advisory.recommended_route_text,
            "severity": advisory.severity.value,
            "published_by": str(advisory.published_by),
            "published_at": advisory.published_at.isoformat(),
        }
    }


@router.post("/{event_id}/cancel")
async def cancel_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """Cancels an event from DRAFT, PREDICTED, or APPROVED."""
    res = await db.execute(select(Event).where(Event.id == event_id))
    event = res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.status in (EventStatus.CLOSED, EventStatus.CANCELLED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Event is already {event.status.value}",
        )

    event.status = EventStatus.CANCELLED
    await db.commit()
    return {"id": str(event.id), "status": event.status.value}
