"""SurakshaNet Audit API (SN-106)
==============================
Admin-only audit viewer and query endpoints.
Strictly restricted to ADMIN role.
All denials are logged with ACCESS_DENIED.
"""

import uuid
import logging
from typing import Optional, List, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database import get_db
from app.models.audit import AuditLog, AuditActorType, AuditResult
from app.models.user import User
from app.services.auth_service import require_role

logger = logging.getLogger("surakshanet.api.audit")
router = APIRouter(prefix="/audit", tags=["Audit"])


class AuditLogResponse(BaseModel):
    id: str
    timestamp: str
    actor_type: str
    actor_id: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    model: Optional[str] = None
    model_version: Optional[str] = None
    confidence: Optional[float] = None
    source: str
    result: str
    correlation_id: Optional[str] = None


class AuditListResponse(BaseModel):
    items: List[AuditLogResponse]
    total: int
    sampling_notice: str


def _serialize_audit(log: AuditLog) -> AuditLogResponse:
    return AuditLogResponse(
        id=str(log.id),
        timestamp=log.timestamp.isoformat() if log.timestamp else "",
        actor_type=log.actor_type.value if hasattr(log.actor_type, "value") else str(log.actor_type),
        actor_id=str(log.actor_id) if log.actor_id else None,
        action=log.action,
        target_type=log.target_type,
        target_id=str(log.target_id) if log.target_id else None,
        input=log.input,
        output=log.output,
        model=log.model,
        model_version=log.model_version,
        confidence=log.confidence,
        source=log.source,
        result=log.result.value if hasattr(log.result, "value") else str(log.result),
        correlation_id=log.correlation_id,
    )


@router.get("", response_model=AuditListResponse)
async def list_audit_logs(
    actor_type: Optional[str] = Query(None, description="Filter by actor type (USER, SYSTEM, AI)"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    result: Optional[str] = Query(None, description="Filter by result (SUCCESS, FAILURE, DENIED)"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    start_time: Optional[datetime] = Query(None, description="Filter records on or after start_time"),
    end_time: Optional[datetime] = Query(None, description="Filter records on or before end_time"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Lists system audit records. Strictly accessible to ADMIN only (SN-106).
    Discloses sampling of high-frequency AI control decisions.
    """
    conditions = []
    if actor_type:
        try:
            conditions.append(AuditLog.actor_type == AuditActorType(actor_type.upper()))
        except ValueError:
            conditions.append(AuditLog.actor_type == actor_type.upper())
    if action:
        conditions.append(AuditLog.action == action.upper())
    if result:
        try:
            conditions.append(AuditLog.result == AuditResult(result.upper()))
        except ValueError:
            conditions.append(AuditLog.result == result.upper())
    if target_type:
        conditions.append(AuditLog.target_type == target_type)
    if start_time:
        conditions.append(AuditLog.timestamp >= start_time)
    if end_time:
        conditions.append(AuditLog.timestamp <= end_time)

    # Total count query
    count_stmt = select(func.count()).select_from(AuditLog)
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total_res = await db.execute(count_stmt)
    total_count = total_res.scalar() or 0

    # Paged query
    stmt = (
        select(AuditLog)
        .order_by(desc(AuditLog.timestamp))
        .offset(offset)
        .limit(limit)
    )
    if conditions:
        stmt = stmt.where(*conditions)

    res = await db.execute(stmt)
    rows = res.scalars().all()

    return AuditListResponse(
        items=[_serialize_audit(r) for r in rows],
        total=total_count,
        sampling_notice=(
            "AI control decisions are sampled in this audit stream (all clamps, mode changes, and "
            "fallbacks, plus 1-in-20 routine decisions). The complete un-sampled stream is retained in control_decisions."
        ),
    )


@router.get("/{audit_id}", response_model=AuditLogResponse)
async def get_audit_log(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """Retrieves single audit record detail by UUID. ADMIN only."""
    res = await db.execute(select(AuditLog).where(AuditLog.id == audit_id))
    log = res.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audit log entry not found")
    return _serialize_audit(log)
