import uuid
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import redis.asyncio as aioredis

from app.database import get_db
from app.config import get_settings
from app.models.vision import (
    BehaviorFlag,
    BehaviorFlagType,
    BehaviorFlagStatus,
    NoParkingZone,
)
from app.models.user import User
from app.models.audit import AuditActorType, AuditResult
from app.services.auth_service import require_role, get_optional_current_user
from app.services.audit_service import write_audit

logger = logging.getLogger("surakshanet.api.vision")
router = APIRouter(prefix="/vision", tags=["Vision"])
settings = get_settings()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FlagResolveRequest(BaseModel):
    status: BehaviorFlagStatus = Field(..., description="Target status: CONFIRMED or DISMISSED")
    note: Optional[str] = Field(None, max_length=256)


class ZoneCreateRequest(BaseModel):
    camera_id: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=128)
    polygon: List[List[float]] = Field(..., min_length=3, description="List of [x, y] coordinates")
    active_start_time: Optional[str] = Field(None, max_length=16, description="HH:MM format")
    active_end_time: Optional[str] = Field(None, max_length=16, description="HH:MM format")


class FlagResponse(BaseModel):
    id: str
    flag_type: str
    camera_id: str
    track_id: str
    detected_at: datetime
    evidence: Dict[str, Any]
    confidence: float
    status: str
    note: str
    resolved_by: Optional[str]
    resolved_at: Optional[datetime]
    source: str


# ---------------------------------------------------------------------------
# Status & Detections (SN-069, SN-073, SN-078)
# ---------------------------------------------------------------------------

@router.get("/status")
async def get_vision_status() -> Dict[str, Any]:
    """Returns live diagnostics of the computer vision worker pipeline (SN-069, SN-073).
    Returns explicit unavailable status when no video source is connected.
    """
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        raw_status = await r.get("vision_worker:status")
        await r.close()
        if raw_status:
            return json.loads(raw_status)
    except Exception as e:
        logger.debug(f"Redis lookup for vision status skipped/failed: {e}")

    # Explicit failure state per SN-073
    return {
        "status": "unavailable",
        "worker_running": False,
        "reason": "no video source configured",
        "fps": None,
        "cameras": [],
    }


@router.get("/detections/latest")
async def get_latest_detections(
    cam_id: str = Query("CAM-01", description="Camera identifier")
) -> Dict[str, Any]:
    """Returns the latest real vehicle detection bounding boxes from the vision worker (SN-078)."""
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        raw = await r.get(f"vision_worker:detections:{cam_id}")
        await r.close()
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"Redis lookup for detections skipped/failed: {e}")

    # Unavailable / offline default
    return {
        "camera_id": cam_id,
        "fps": None,
        "detections": [],
        "counts": {"cars": 0, "buses": 0, "bikes": 0, "pedestrians": 0},
        "timestamp": None,
    }


# ---------------------------------------------------------------------------
# Behavior Flags (SN-076, SN-077, SN-080, SN-081)
# ---------------------------------------------------------------------------

@router.get("/flags")
async def list_behavior_flags(
    camera_id: Optional[str] = None,
    status_filter: Optional[BehaviorFlagStatus] = Query(None, alias="status"),
    flag_type: Optional[BehaviorFlagType] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> List[Dict[str, Any]]:
    """Lists behavior suspicion flags flagged by computer vision detectors."""
    query = select(BehaviorFlag).order_by(desc(BehaviorFlag.detected_at))
    if camera_id:
        query = query.where(BehaviorFlag.camera_id == camera_id)
    if status_filter:
        query = query.where(BehaviorFlag.status == status_filter)
    if flag_type:
        query = query.where(BehaviorFlag.flag_type == flag_type)

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    flags = result.scalars().all()

    return [
        {
            "id": str(f.id),
            "flag_type": f.flag_type.value if hasattr(f.flag_type, "value") else str(f.flag_type),
            "camera_id": f.camera_id,
            "track_id": f.track_id,
            "detected_at": f.detected_at.isoformat(),
            "evidence": f.evidence,
            "confidence": f.confidence,
            "status": f.status.value if hasattr(f.status, "value") else str(f.status),
            "note": f.note,
            "resolved_by": str(f.resolved_by) if f.resolved_by else None,
            "resolved_at": f.resolved_at.isoformat() if f.resolved_at else None,
            "source": f.source,
        }
        for f in flags
    ]


@router.patch("/flags/{flag_id}/resolve")
async def resolve_behavior_flag(
    flag_id: str,
    payload: FlagResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
) -> Dict[str, Any]:
    """Human Gate: Operator resolves or dismisses a flagged suspicious behavior (SN-077).
    Requires authenticated operator action and logs a mandatory audit record.
    """
    try:
        uid = uuid.UUID(flag_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid flag UUID format")

    result = await db.execute(select(BehaviorFlag).where(BehaviorFlag.id == uid))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Behavior flag not found")

    if payload.status not in (BehaviorFlagStatus.CONFIRMED, BehaviorFlagStatus.DISMISSED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be resolved to CONFIRMED or DISMISSED"
        )

    # Set operator resolution fields before setting status to satisfy @validates invariant
    flag.resolved_by = current_user.id
    flag.resolved_at = datetime.utcnow()
    flag.status = payload.status
    if payload.note:
        flag.note = payload.note

    # Write audit log entry (SN-077, SN-124)
    await write_audit(
        db=db,
        action="FLAG_RESOLVE",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="behavior_flag",
        target_id=flag.id,
        input_payload={"target_status": payload.status.value, "note": payload.note},
        output_payload={"resolved_at": flag.resolved_at.isoformat(), "flag_type": str(flag.flag_type)},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    await db.commit()
    await db.refresh(flag)

    return {
        "id": str(flag.id),
        "flag_type": flag.flag_type.value if hasattr(flag.flag_type, "value") else str(flag.flag_type),
        "camera_id": flag.camera_id,
        "track_id": flag.track_id,
        "status": flag.status.value if hasattr(flag.status, "value") else str(flag.status),
        "resolved_by": str(flag.resolved_by),
        "resolved_at": flag.resolved_at.isoformat() if flag.resolved_at else None,
        "note": flag.note,
    }


# ---------------------------------------------------------------------------
# Restricted Zones (SN-079)
# ---------------------------------------------------------------------------

@router.post("/zones", status_code=status.HTTP_201_CREATED)
async def create_restricted_zone(
    payload: ZoneCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
) -> Dict[str, Any]:
    """Operator endpoint to create and configure a restricted no-parking zone polygon (SN-079)."""
    zone = NoParkingZone(
        id=uuid.uuid4(),
        camera_id=payload.camera_id,
        name=payload.name,
        polygon=payload.polygon,
        active_start_time=payload.active_start_time,
        active_end_time=payload.active_end_time,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(zone)

    await write_audit(
        db=db,
        action="ZONE_CREATE",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="no_parking_zone",
        target_id=zone.id,
        input_payload={"camera_id": payload.camera_id, "name": payload.name},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    await db.commit()
    await db.refresh(zone)

    return {
        "id": str(zone.id),
        "camera_id": zone.camera_id,
        "name": zone.name,
        "polygon": zone.polygon,
        "active_start_time": zone.active_start_time,
        "active_end_time": zone.active_end_time,
        "created_at": zone.created_at.isoformat(),
    }


@router.get("/zones")
async def list_restricted_zones(
    camera_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> List[Dict[str, Any]]:
    """Lists restricted no-parking zones configured for cameras."""
    query = select(NoParkingZone).order_by(desc(NoParkingZone.created_at))
    if camera_id:
        query = query.where(NoParkingZone.camera_id == camera_id)

    result = await db.execute(query)
    zones = result.scalars().all()

    return [
        {
            "id": str(z.id),
            "camera_id": z.camera_id,
            "name": z.name,
            "polygon": z.polygon,
            "active_start_time": z.active_start_time,
            "active_end_time": z.active_end_time,
            "created_at": z.created_at.isoformat(),
        }
        for z in zones
    ]
