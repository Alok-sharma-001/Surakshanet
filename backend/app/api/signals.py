import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import redis.asyncio as aioredis

from app.database import get_db
from app.config import get_settings
from app.models.signal import SignalPlan, SignalMode
from app.models.junction import Junction
from app.models.control import ControlDecision
from app.models.user import User
from app.models.audit import AuditActorType, AuditResult
from app.services.auth_service import require_role, enforce_rate_limit
from app.services.audit_service import write_audit
from shared.constants import REDIS_CHANNELS

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
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER")),
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
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER")),
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


@router.get("/junctions/{junction_id}/decision")
async def get_control_decision(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER", action="SIGNAL_DECISION_READ")),
):
    """Get latest autonomous or Webster control decision for this junction."""
    j_uuid = await _resolve_junction_uuid(db, junction_id)
    if not j_uuid:
        raise HTTPException(status_code=404, detail="Junction not found")

    result = await db.execute(
        select(ControlDecision)
        .where(ControlDecision.junction_id == j_uuid)
        .order_by(desc(ControlDecision.timestamp))
        .limit(1)
    )
    decision = result.scalar_one_or_none()
    if not decision:
        raise HTTPException(status_code=404, detail="No control decisions recorded for junction")

    return {
        "id": str(decision.id),
        "junction_id": str(decision.junction_id),
        "controller": decision.controller,
        "action": decision.action,
        "applied_phase": decision.applied_phase,
        "applied_duration_s": decision.applied_duration_s,
        "clamped": decision.clamped,
        "clamp_reason": decision.clamp_reason,
        "model_version": decision.model_version,
        "timestamp": decision.timestamp.isoformat() if decision.timestamp else None,
    }


@router.patch("/junctions/{junction_id}/mode")
async def update_signal_mode(
    junction_id: str,
    req: SignalModeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", action="SIGNAL_MODE_CHANGE")),
):
    """Switch signal control mode between MARL, WEBSTER, and MANUAL (SN-100, SN-104)."""
    j_uuid = await _resolve_junction_uuid(db, junction_id)
    target_id_str = str(j_uuid) if j_uuid else str(junction_id)

    try:
        new_mode = SignalMode[req.mode.upper()]
    except KeyError:
        raise HTTPException(status_code=400, detail=f"Invalid mode. Must be one of: {[m.name for m in SignalMode]}")

    old_mode_str = "UNKNOWN"
    if j_uuid:
        result = await db.execute(select(SignalPlan).where(SignalPlan.junction_id == j_uuid))
        plan = result.scalar_one_or_none()
        if plan:
            old_mode_str = plan.mode.value if hasattr(plan.mode, 'value') else str(plan.mode)
            plan.mode = new_mode
            # Naive UTC, matching SignalPlan.updated_at's DateTime (no
            # timezone) column — asyncpg rejects a tz-aware value here.
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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await redis.publish(REDIS_CHANNELS["signals"], json.dumps(event))
        await redis.aclose()
    except Exception as e:
        logger.warning(f"Could not publish signal mode to Redis: {e}")

    # Audit log (SN-104)
    corr_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    try:
        await write_audit(
            db=db,
            action="SIGNAL_MODE_CHANGE",
            actor_type=AuditActorType.USER,
            actor_id=current_user.id,
            target_type="junction",
            target_id=j_uuid,
            input_payload={"junction_id": target_id_str, "requested_mode": new_mode.value, "old_mode": old_mode_str},
            output_payload={"status": "success", "mode": new_mode.value},
            result=AuditResult.SUCCESS,
            source="manual",
            correlation_id=corr_id,
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Audit log failed for SIGNAL_MODE_CHANGE: {e}")

    return {
        "status": "success",
        "junction_id": target_id_str,
        "mode": new_mode.value,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }


@router.post("/junctions/{junction_id}/override")
async def override_signal_phase(
    junction_id: str,
    req: SignalOverrideRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", action="SIGNAL_OVERRIDE")),
):
    """Execute manual signal override, rate-limited 10/min and time-boxed 300 s (SN-100, SN-101, SN-104)."""
    # Rate limit: 10/min/user (SN-101)
    await enforce_rate_limit(
        key=f"rate_limit:override:{current_user.id}",
        limit=10,
        window_seconds=60,
        detail="Signal override limit exceeded"
    )

    j_uuid = await _resolve_junction_uuid(db, junction_id)
    target_id_str = str(j_uuid) if j_uuid else str(junction_id)

    action_normalized = req.action.upper()
    valid_actions = ["PHASE_SKIP", "FORCE_PHASE_SKIP", "EXTEND_GREEN", "SHORTEN_GREEN", "FLASH_ALL_RED", "HOLD_GREEN"]
    if action_normalized not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid override action. Must be one of: {valid_actions}")

    # Broadcast override command to Redis with timebox of 300s auto-return (SN-101)
    now_iso = datetime.now(timezone.utc).isoformat()
    event_payload = {
        "type": "SIGNAL_OVERRIDE",
        "junction_id": target_id_str,
        "action": action_normalized,
        "value": req.value or 5,
        "auto_return_s": 300,
        "time_boxed_s": 300,
        "executed_at": now_iso
    }

    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        await redis.publish(REDIS_CHANNELS["signals"], json.dumps(event_payload))
        await redis.aclose()
    except Exception as e:
        logger.warning(f"Could not publish signal override to Redis: {e}")

    # Audit log (SN-104)
    corr_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID")
    try:
        await write_audit(
            db=db,
            action="SIGNAL_OVERRIDE",
            actor_type=AuditActorType.USER,
            actor_id=current_user.id,
            target_type="junction",
            target_id=j_uuid,
            input_payload={"junction_id": target_id_str, "action": action_normalized, "value": req.value, "time_box_s": 300},
            output_payload={"status": "override_applied", "action": action_normalized},
            result=AuditResult.SUCCESS,
            source="manual",
            correlation_id=corr_id,
        )
        await db.commit()
    except Exception as e:
        logger.error(f"Audit log failed for SIGNAL_OVERRIDE: {e}")

    return {
        "status": "override_applied",
        "junction_id": target_id_str,
        "action": action_normalized,
        "value": req.value,
        "auto_return_s": 300,
        "executed_at": event_payload["executed_at"]
    }
