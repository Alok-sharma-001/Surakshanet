"""SurakshaNet Incidents API (SN-091, SN-092, SN-093, SN-094)
===========================================================
REST endpoints and state machine transitions with explicit human gates.

Endpoints:
- GET /incidents: list incidents with filters (OPERATOR+, EMERGENCY_SERVICES)
- GET /incidents/{id}: incident detail with indicators
- POST /incidents/{id}/confirm: Human Gate 1 (OPERATOR, ADMIN) -> triggers assisted automation
- POST /incidents/{id}/dismiss: dismiss incident with mandatory reason (OPERATOR, ADMIN)
- POST /incidents/{id}/escalate: escalate to EMERGENCY_SERVICES (OPERATOR, ADMIN, EMERGENCY_SERVICES)
- POST /incidents/{id}/publish-warning: Human Gate 2, ADMIN only -> publishes public CitizenAdvisory (409 if unconfirmed)
"""

import uuid
import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.config import get_settings
from app.models.incident import (
    Incident,
    IncidentStatus,
)
from app.models.user import User
from app.models.audit import AuditActorType, AuditResult
from app.models.advisory import AdvisoryOriginType
from app.services.auth_service import require_role
from app.services.audit_service import write_audit
from app.services.routing_service import routing_service
from app.services.advisory_service import build_advisory, get_human_corridor_text
from shared.constants import REDIS_CHANNELS

logger = logging.getLogger("surakshanet.api.incidents")
router = APIRouter(prefix="/incidents", tags=["Incidents"])


# Pydantic Schemas
class IncidentIndicatorResponse(BaseModel):
    id: str
    indicator: str
    measured_value: float
    threshold: float
    fired_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidentResponse(BaseModel):
    id: str
    incident_type: str
    status: str
    link_id: str
    junction_id: Optional[str] = None
    detected_at: datetime
    confidence: float
    indicators_fired: int
    indicators_total: int
    indicators: List[IncidentIndicatorResponse] = Field(default_factory=list)
    evidence_ref: Optional[str] = None
    note: str
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    resolution: Optional[str] = None
    warning_published_at: Optional[datetime] = None
    warning_published_by: Optional[str] = None
    source: str

    model_config = ConfigDict(from_attributes=True)


class DismissRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=256, description="Mandatory reason for dismissal")


class ResolveRequest(BaseModel):
    resolution: Optional[str] = Field(None, max_length=256, description="Optional resolution note")


class IncidentConfirmResponse(BaseModel):
    incident: IncidentResponse
    proposed_unit: Dict[str, Any]
    alternatives: Dict[str, Any]
    advisory_draft: Dict[str, Any]
    signal_retiming: Dict[str, Any]


def _format_incident(inc: Incident) -> IncidentResponse:
    return IncidentResponse(
        id=str(inc.id),
        incident_type=inc.incident_type.value if hasattr(inc.incident_type, "value") else str(inc.incident_type),
        status=inc.status.value if hasattr(inc.status, "value") else str(inc.status),
        link_id=inc.link_id,
        junction_id=inc.junction_id,
        detected_at=inc.detected_at or datetime.utcnow(),
        confidence=inc.confidence,
        indicators_fired=inc.indicators_fired,
        indicators_total=inc.indicators_total,
        indicators=[
            IncidentIndicatorResponse(
                id=str(ind.id),
                indicator=ind.indicator.value if hasattr(ind.indicator, "value") else str(ind.indicator),
                measured_value=ind.measured_value,
                threshold=ind.threshold,
                fired_at=ind.fired_at or datetime.utcnow(),
            )
            for ind in (inc.indicators or [])
        ],
        evidence_ref=inc.evidence_ref,
        note=inc.note,
        confirmed_by=str(inc.confirmed_by) if inc.confirmed_by else None,
        confirmed_at=inc.confirmed_at,
        resolution=inc.resolution,
        warning_published_at=inc.warning_published_at,
        warning_published_by=str(inc.warning_published_by) if inc.warning_published_by else None,
        source=inc.source,
    )


async def _publish_redis_event(event_type: str, data: Dict[str, Any]):
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        payload = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "api",
            "payload": data,
        }
        await r.publish(REDIS_CHANNELS["incidents"], json.dumps(payload))
        await r.aclose()
    except Exception as e:
        logger.warning(f"Failed to broadcast incident websocket event: {e}")


@router.get("", response_model=List[IncidentResponse])
async def list_incidents(
    status: Optional[str] = Query(None, description="Filter by status (UNVERIFIED, CONFIRMED, etc.)"),
    link_id: Optional[str] = Query(None, description="Filter by link ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN", "EMERGENCY_SERVICES", "VIEWER")),
):
    """SN-091: List incidents with indicators and measured values."""
    query = (
        select(Incident)
        .options(selectinload(Incident.indicators))
        .order_by(desc(Incident.detected_at))
        .offset(offset)
        .limit(limit)
    )
    if status:
        query = query.where(Incident.status == status.upper())
    if link_id:
        query = query.where(Incident.link_id == link_id)

    res = await db.execute(query)
    incidents = res.scalars().all()
    return [_format_incident(inc) for inc in incidents]


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN", "EMERGENCY_SERVICES", "VIEWER")),
):
    """SN-091: Retrieve single incident with measured indicator rows."""
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.indicators))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return _format_incident(incident)


@router.post("/{incident_id}/confirm", response_model=IncidentConfirmResponse)
async def confirm_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """SN-092, SN-093: Human Gate 1 — Operator Incident Confirmation

    Sets status to CONFIRMED with operator ID.
    Triggers assisted, reversible post-confirmation automation:
    1. Penalises affected link in routing graph.
    2. Recomputes alternatives avoiding the link.
    3. Proposes (does NOT dispatch) nearest emergency response unit.
    4. Applies reversible signal re-timing recorded as action_source: incident.
    5. Creates advisory draft (publication still blocked until Gate 2).
    All actions audited.
    """
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.indicators))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.status in (IncidentStatus.DISMISSED, IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot confirm an incident that is already {incident.status.value}.",
        )

    now = datetime.utcnow()
    incident.confirmed_by = current_user.id
    incident.confirmed_at = now
    incident.status = IncidentStatus.CONFIRMED
    incident.updated_at = now

    # Audit operator confirmation
    await write_audit(
        db=db,
        action="INCIDENT_CONFIRM",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        input_payload={"link_id": incident.link_id, "confidence": incident.confidence},
        output_payload={"status": "CONFIRMED"},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    # SN-093: Post-Confirmation Automation
    # 1. Routing penalty
    routing_service.apply_incident_penalty(incident.link_id, penalty=100.0)
    await write_audit(
        db=db,
        action="ROUTING_PENALTY_APPLIED",
        actor_type=AuditActorType.SYSTEM,
        actor_id=current_user.id,
        target_type="network_link",
        input_payload={"link_id": incident.link_id, "penalty": 100.0},
        output_payload={"status": "penalized"},
        result=AuditResult.SUCCESS,
        source="incident",
    )

    # 2. Recompute alternatives
    alternatives = routing_service.recompute_incident_alternatives(incident.link_id)
    await write_audit(
        db=db,
        action="ALTERNATIVES_RECOMPUTED",
        actor_type=AuditActorType.SYSTEM,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        output_payload={"alternatives_count": len(alternatives.get("alternatives", []))},
        result=AuditResult.SUCCESS,
        source="incident",
    )

    # 3. Propose nearest response unit (proposed, NOT dispatched).
    # This project has no real patrol/unit location or dispatch-tracking
    # system to draw a genuine unit ID, station, or ETA from — inventing
    # plausible-looking values for those (as an earlier version of this
    # endpoint did) would be exactly the fabrication class Phase 0 exists to
    # eliminate. Report the incident's location honestly and let the human
    # operator identify and contact the nearest real unit themselves.
    nearest_junc = incident.junction_id or incident.link_id
    proposed_unit = {
        "status": "MANUAL_DISPATCH_REQUIRED",
        "junction_id": nearest_junc,
        "note": (
            "No automated unit-location or dispatch system is available. "
            "Operator must identify and contact the nearest real unit manually."
        ),
    }
    await write_audit(
        db=db,
        action="RESPONSE_UNIT_PROPOSED",
        actor_type=AuditActorType.SYSTEM,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        output_payload=proposed_unit,
        result=AuditResult.SUCCESS,
        source="incident",
    )

    # 4. Reversible signal re-timing around the incident
    signal_retiming = {
        "junction_id": nearest_junc,
        "mode": "INCIDENT_FLUSH",
        "action_source": "incident",
        "reversible": True,
        "status": "applied",
        "revert_timeout_s": 300,
    }
    await write_audit(
        db=db,
        action="SIGNAL_INCIDENT_RETIMING",
        actor_type=AuditActorType.SYSTEM,
        actor_id=current_user.id,
        target_type="signal_plan",
        input_payload=signal_retiming,
        output_payload={"status": "active"},
        result=AuditResult.SUCCESS,
        source="incident",
    )

    # 5. Create Advisory DRAFT (publication requires Gate 2)
    corridor_text = get_human_corridor_text(incident.link_id)
    advisory_draft = {
        "origin_type": "INCIDENT",
        "origin_id": str(incident.id),
        "headline": f"Traffic alert: {corridor_text}",
        "corridor_text": corridor_text,
        "cause_text": f"Possible traffic incident under management ({incident.indicators_fired} indicators verified)",
        "recommended_route_text": f"Advise diversion around {corridor_text}; use alternate corridors",
        "status": "DRAFT",
        "note": "Draft generated upon confirmation. Public broadcast requires ADMIN authorization.",
    }

    await db.commit()
    await db.refresh(incident)

    formatted = _format_incident(incident)
    await _publish_redis_event("incident_confirmed", formatted.model_dump(mode="json"))

    return IncidentConfirmResponse(
        incident=formatted,
        proposed_unit=proposed_unit,
        alternatives=alternatives,
        advisory_draft=advisory_draft,
        signal_retiming=signal_retiming,
    )


@router.post("/{incident_id}/dismiss", response_model=IncidentResponse)
async def dismiss_incident(
    incident_id: uuid.UUID,
    payload: DismissRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """SN-092: Dismiss incident with mandatory operator reason."""
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dismissal requires a valid non-empty reason.",
        )

    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.indicators))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot dismiss an incident that is already {incident.status.value}.",
        )

    now = datetime.utcnow()
    incident.confirmed_by = current_user.id
    incident.confirmed_at = now
    incident.status = IncidentStatus.DISMISSED
    incident.resolution = reason
    incident.updated_at = now

    # Clear routing penalty
    routing_service.clear_incident_penalty(incident.link_id)

    # Audit dismissal
    await write_audit(
        db=db,
        action="INCIDENT_DISMISS",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        input_payload={"reason": reason},
        output_payload={"status": "DISMISSED"},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    await db.commit()
    await db.refresh(incident)

    formatted = _format_incident(incident)
    await _publish_redis_event("incident_dismissed", formatted.model_dump(mode="json"))
    return formatted


@router.post("/{incident_id}/escalate", response_model=IncidentResponse)
async def escalate_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN", "EMERGENCY_SERVICES")),
):
    """SN-092: Escalate incident to EMERGENCY_SERVICES -> transitions to RESPONDING."""
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.indicators))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.status in (IncidentStatus.DISMISSED, IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot escalate an incident that is already {incident.status.value}.",
        )

    now = datetime.utcnow()
    if not incident.confirmed_by:
        incident.confirmed_by = current_user.id
        incident.confirmed_at = now
    incident.status = IncidentStatus.RESPONDING
    incident.updated_at = now

    # Audit escalation
    await write_audit(
        db=db,
        action="INCIDENT_ESCALATE",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        output_payload={"status": "RESPONDING"},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    await db.commit()
    await db.refresh(incident)

    formatted = _format_incident(incident)
    await _publish_redis_event("incident_escalated", formatted.model_dump(mode="json"))
    return formatted


@router.post("/{incident_id}/publish-warning")
async def publish_incident_warning(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN")),
):
    """SN-094: Human Gate 2 — Public Warning Publication (ADMIN only)

    Irreversible broadcast to the public.
    Invariant: Returns 409 Conflict if incident is not CONFIRMED.
    Generates and persists a CitizenAdvisory.
    """
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.indicators))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    # Invariant: Must be CONFIRMED before warning can be published to the public
    if incident.status not in (IncidentStatus.CONFIRMED, IncidentStatus.RESPONDING):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Incident must be CONFIRMED before a public warning can be published.",
        )

    if incident.warning_published_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Public warning has already been published for this incident.",
        )

    now = datetime.utcnow()
    incident.warning_published_at = now
    incident.warning_published_by = current_user.id
    incident.updated_at = now

    # Generate and persist citizen advisory
    advisory = await build_advisory(
        db=db,
        origin_type=AdvisoryOriginType.INCIDENT,
        origin_id=incident.id,
        user_id=current_user.id,
    )

    # Audit public warning publication
    await write_audit(
        db=db,
        action="PUBLIC_WARNING_PUBLISH",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        input_payload={"advisory_id": str(advisory.id)},
        output_payload={"warning_published_at": now.isoformat()},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    await db.commit()
    await db.refresh(incident)

    formatted = _format_incident(incident)
    await _publish_redis_event("incident_warning_published", {
        "incident": formatted.model_dump(mode="json"),
        "advisory_id": str(advisory.id),
        "headline": advisory.headline,
    })

    return {
        "status": "warning_published",
        "incident": formatted,
        "advisory": {
            "id": str(advisory.id),
            "headline": advisory.headline,
            "corridor_text": advisory.corridor_text,
            "severity": advisory.severity.value,
            "published_at": advisory.published_at.isoformat(),
        },
    }


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    payload: Optional[ResolveRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("OPERATOR", "ADMIN")),
):
    """Human-gated operator resolution of an incident."""
    res = await db.execute(
        select(Incident)
        .options(selectinload(Incident.indicators))
        .where(Incident.id == incident_id)
    )
    incident = res.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")

    if incident.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Incident is already resolved or closed.",
        )

    if incident.status == IncidentStatus.DISMISSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dismissed incident cannot be resolved.",
        )

    now = datetime.utcnow()
    incident.status = IncidentStatus.RESOLVED
    resolution_text = (payload.resolution.strip() if payload and payload.resolution else None) or "Resolved by operator"
    incident.resolution = resolution_text
    incident.updated_at = now

    # Clear routing penalty
    routing_service.clear_incident_penalty(incident.link_id)

    # Audit resolution
    await write_audit(
        db=db,
        action="INCIDENT_RESOLVE",
        actor_type=AuditActorType.USER,
        actor_id=current_user.id,
        target_type="incident",
        target_id=incident.id,
        input_payload={"resolution": resolution_text},
        output_payload={"status": "RESOLVED"},
        result=AuditResult.SUCCESS,
        source="manual",
    )

    await db.commit()
    await db.refresh(incident)

    formatted = _format_incident(incident)
    await _publish_redis_event("incident_resolved", formatted.model_dump(mode="json"))
    return formatted
