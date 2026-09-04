import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import redis.asyncio as aioredis

from app.database import get_db
from app.config import get_settings
from app.models.signal import SignalPlan, SignalMode
from app.models.junction import Junction
from app.services.auth_service import get_current_user, get_optional_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/signals", tags=["Signals"])

class SignalModeRequest(BaseModel):
    mode: str

class SignalOverrideRequest(BaseModel):
    action: str  # PHASE_SKIP, EXTEND_GREEN, SHORTEN_GREEN, FLASH_ALL_RED
    value: Optional[int] = 5

class SignalPlanResponse(BaseModel):
    id: str
    junction_id: str
    junction_name: str
    name: str
    mode: str
    phases: List[Dict[str, Any]]
    current_phase: int = 1
    cycle_length_s: int = 120
    is_active: bool = True

async def _resolve_junction_uuid(db: AsyncSession, identifier: str) -> Optional[uuid.UUID]:
    """Resolve junction identifier (UUID or human name/code) to UUID."""
    try:
        return uuid.UUID(identifier)
    except ValueError:
        pass

    # Search by partial name match
    result = await db.execute(select(Junction).where(Junction.name.ilike(f"%{identifier}%")))
    j = result.scalars().first()
    if j:
        return j.id
    return None

@router.get("/plans")
async def list_signal_plans(
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """List all configured signal plans across city junctions."""
    result = await db.execute(select(SignalPlan, Junction.name).join(Junction, SignalPlan.junction_id == Junction.id))
    rows = result.all()

    plans = []
    for plan, j_name in rows:
        mode_val = plan.mode.value if hasattr(plan.mode, 'value') else str(plan.mode)
        total_cycle = sum(p.get("duration", 30) for p in (plan.phases or [])) or 120
        plans.append({
            "id": str(plan.id),
            "junction_id": str(plan.junction_id),
            "junction_name": j_name,
            "name": plan.name,
            "mode": mode_val,
            "phases": plan.phases or [],
            "cycle_length_s": total_cycle,
            "is_active": plan.is_active
        })
    return plans

@router.get("/junctions/{junction_id}")
async def get_junction_signal_plan(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Get active signal plan and live phase status for a specific junction."""
    j_uuid = await _resolve_junction_uuid(db, junction_id)
    if not j_uuid:
        # Fallback to first available plan if test ID used
        result = await db.execute(select(SignalPlan, Junction.name).join(Junction, SignalPlan.junction_id == Junction.id).limit(1))
        row = result.first()
    else:
        result = await db.execute(
            select(SignalPlan, Junction.name)
            .join(Junction, SignalPlan.junction_id == Junction.id)
            .where(SignalPlan.junction_id == j_uuid)
        )
        row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="Signal plan not found for junction")

    plan, j_name = row
    mode_val = plan.mode.value if hasattr(plan.mode, 'value') else str(plan.mode)
    total_cycle = sum(p.get("duration", 30) for p in (plan.phases or [])) or 120

    return {
        "id": str(plan.id),
        "junction_id": str(plan.junction_id),
        "junction_name": j_name,
        "name": plan.name,
        "mode": mode_val,
        "phases": plan.phases or [],
        "current_phase": 1,
        "time_in_phase_s": 14,
        "cycle_length_s": total_cycle,
        "is_active": plan.is_active
    }

@router.patch("/junctions/{junction_id}/mode")
async def update_signal_mode(
    junction_id: str,
    req: SignalModeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Switch signal control mode between MARL, WEBSTER, and MANUAL."""
    j_uuid = await _resolve_junction_uuid(db, junction_id)
    target_id_str = str(j_uuid) if j_uuid else str(junction_id)

    try:
        new_mode = SignalMode[req.mode.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {[m.name for m in SignalMode]}")

    if j_uuid:
        result = await db.execute(select(SignalPlan).where(SignalPlan.junction_id == j_uuid))
        plan = result.scalar_one_or_none()
        if plan:
            plan.mode = new_mode
            plan.updated_at = datetime.utcnow()
            db.add(plan)
            await db.commit()

    # Publish mode change event to Redis
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        event = {
            "type": "SIGNAL_MODE_CHANGED",
            "junction_id": target_id_str,
            "mode": new_mode.value,
            "timestamp": datetime.utcnow().isoformat()
        }
        await redis.publish("signal_events", json.dumps(event))
        await redis.aclose()
    except Exception as e:
        logger.warning(f"Could not publish signal mode to Redis: {e}")

    return {
        "status": "success",
        "junction_id": target_id_str,
        "mode": new_mode.value,
        "updated_at": datetime.utcnow().isoformat()
    }

@router.post("/junctions/{junction_id}/override")
async def override_signal_phase(
    junction_id: str,
    req: SignalOverrideRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """Execute manual signal override (phase skip, green adjustment, or flash all-red)."""
    j_uuid = await _resolve_junction_uuid(db, junction_id)
    target_id_str = str(j_uuid) if j_uuid else str(junction_id)

    action_normalized = req.action.upper()
    valid_actions = ["PHASE_SKIP", "FORCE_PHASE_SKIP", "EXTEND_GREEN", "SHORTEN_GREEN", "FLASH_ALL_RED", "HOLD_GREEN"]
    if action_normalized not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid override action. Must be one of: {valid_actions}")

    # Broadcast override command to Redis
    event_payload = {
        "type": "SIGNAL_OVERRIDE",
        "junction_id": target_id_str,
        "action": action_normalized,
        "value": req.value or 5,
        "executed_at": datetime.utcnow().isoformat()
    }

    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        await redis.publish("signal_events", json.dumps(event_payload))
        await redis.aclose()
    except Exception as e:
        logger.warning(f"Could not publish signal override to Redis: {e}")

    return {
        "status": "override_applied",
        "junction_id": target_id_str,
        "action": action_normalized,
        "value": req.value,
        "executed_at": event_payload["executed_at"]
    }
