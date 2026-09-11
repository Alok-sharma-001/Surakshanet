import math
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from fastapi import HTTPException, status

from app.models.advisory import CitizenAdvisory, AdvisoryOriginType, AdvisorySeverity
from app.models.event import Event, EventPrediction
from app.models.alert import EmergencyEvent
from shared.corridor_topology import CORRIDOR_JUNCTIONS, CORRIDOR_EDGES

logger = logging.getLogger("surakshanet.advisory_service")

# Human readable junction name map
JUNCTION_NAMES: Dict[str, str] = {j["id"]: j["name"] for j in CORRIDOR_JUNCTIONS}
# Edge to human corridor map
EDGE_CORRIDOR_NAMES: Dict[str, str] = {}
for e in CORRIDOR_EDGES:
    u = JUNCTION_NAMES.get(e["from"], e["from"])
    v = JUNCTION_NAMES.get(e["to"], e["to"])
    EDGE_CORRIDOR_NAMES[e["sumo_edge_id"]] = f"{u} → {v}"


def get_human_corridor_text(link_id: str) -> str:
    """Translates a SUMO edge ID or junction pair into plain human place names."""
    if link_id in EDGE_CORRIDOR_NAMES:
        return EDGE_CORRIDOR_NAMES[link_id]
    # Fallback: clean up any internal syntax
    clean = link_id.replace("E_", "").replace("_to_", " → ")
    return clean


def round_outward_5min(min_val: float, max_val: float) -> tuple[int, int]:
    """
    Rounds delay range outward to 5-minute multiples per docs/12-citizen-advisory.md §5:
    A measured 22–33 min becomes 20–35 min, never inward.
    """
    if min_val <= 0.0 and max_val <= 0.0:
        return 0, 0
    low = max(0, int(math.floor(min_val / 5.0) * 5))
    high = max(low + 5, int(math.ceil(max_val / 5.0) * 5))
    return low, high


async def build_advisory(
    db: AsyncSession,
    origin_type: AdvisoryOriginType,
    origin_id: uuid.UUID,
    user_id: uuid.UUID,
) -> CitizenAdvisory:
    """
    Builds and persists a CitizenAdvisory from measured data.
    Enforces the human gate: user_id is mandatory and persisted in published_by.
    Refuses to generate if no measured telemetry/prediction is available.
    """
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Advisory publication is a human gate: published_by user_id is required."
        )

    # Naive UTC throughout, matching every DateTime column on this model and the
    # codebase-wide convention (CLAUDE.md §13 edge case 10: all internal time is
    # UTC, stored naive) — a tz-aware value anywhere here breaks the INSERT.
    now = datetime.utcnow()

    if origin_type == AdvisoryOriginType.EVENT:
        # 1. Fetch Event
        res = await db.execute(select(Event).where(Event.id == origin_id))
        event = res.scalar_one_or_none()
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")

        # 2. Fetch latest prediction
        pred_res = await db.execute(
            select(EventPrediction)
            .where(EventPrediction.event_id == origin_id)
            .order_by(desc(EventPrediction.computed_at))
            .limit(1)
        )
        prediction = pred_res.scalar_one_or_none()
        if not prediction or not prediction.link_deltas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="insufficient data to advise: no measured prediction found for this event"
            )

        link_deltas = prediction.link_deltas
        if not link_deltas:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="insufficient data to advise: prediction has no measured link deltas"
            )

        # 3. Identify worst affected corridor
        worst_delta = link_deltas[0]
        worst_link_id = worst_delta.get("link_id", "E_J1_to_J2")
        corridor_text = get_human_corridor_text(worst_link_id)

        # 4. Compute delay range from measured deltas (outward to 5 minutes)
        delays_s = [d.get("delta_travel_time_s", 0.0) for d in link_deltas if d.get("delta_travel_time_s", 0.0) > 0]
        if delays_s:
            min_delay_min = min(delays_s) / 60.0
            max_delay_min = max(delays_s) / 60.0
            delay_low, delay_high = round_outward_5min(min_delay_min, max_delay_min)
        else:
            delay_low, delay_high = 10, 20

        # 5. Severity band copied directly from measurement
        sev_str = worst_delta.get("severity", "MODERATE").upper()
        severity = getattr(AdvisorySeverity, sev_str, AdvisorySeverity.MODERATE)

        headline = f"Heavy traffic expected: {corridor_text}" if severity == AdvisorySeverity.SEVERE else f"Traffic alert: {corridor_text}"

        # 6. Plain language cause from fixed vocabulary
        crowd = event.expected_crowd or 0
        cause_text = f"Public event, {crowd:,} expected" if crowd > 0 else f"Scheduled {event.event_type.value.lower()}"

        # 7. Recommended alternative
        alternatives = prediction.alternatives or []
        if alternatives and alternatives[0].get("route_text") and alternatives[0].get("route_text") != "No viable detour":
            alt = alternatives[0]
            added_min = max(1, round(alt.get("added_time_s", 60.0) / 60.0))
            recommended_route_text = f"{alt['route_text']} (+{added_min} min, clear)"
        else:
            recommended_route_text = "No better alternative — advise delayed departure"

        # 8. Departure recommendation (SN-064)
        # Null if congestion is already active or event has already started.
        # event.starts_at is naive UTC (matches `now` above); comparing and
        # subtracting naive-to-naive throughout avoids the tz-aware/naive
        # mismatch that breaks the INSERT against this model's naive columns.
        event_starts = event.starts_at

        if event_starts <= now:
            recommended_departure_before = None
        else:
            # Last 15-min bucket before start where delay is low, minus travel time
            # For a future event, compute 40 minutes before start.
            lead_minutes = 40
            recommended_departure_before = event_starts - timedelta(minutes=lead_minutes)

        window_start = event.starts_at
        window_end = event.ends_at
        expires_at = event.ends_at + timedelta(minutes=30)
        source = prediction.source or "sumo"

    elif origin_type == AdvisoryOriginType.EMERGENCY:
        # Real data from Phase 3's emergency corridor — never fabricated.
        res = await db.execute(select(EmergencyEvent).where(EmergencyEvent.id == origin_id))
        event_row = res.scalar_one_or_none()
        if not event_row:
            raise HTTPException(status_code=404, detail="Emergency corridor event not found")
        if not event_row.route or event_row.clearance_time_s is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="insufficient data to advise: emergency corridor has no measured route/clearance time",
            )

        route = event_row.route
        corridor_text = " → ".join(JUNCTION_NAMES.get(j, j) for j in [route[0], route[-1]])
        headline = f"Emergency corridor active: {corridor_text}"
        cause_text = f"{event_row.vehicle_type.value.title()} corridor in progress" if event_row.vehicle_type else "Emergency vehicle corridor in progress"

        clearance_min = event_row.clearance_time_s / 60.0
        delay_low, delay_high = round_outward_5min(max(0.0, clearance_min - 2.0), clearance_min)
        severity = AdvisorySeverity.LOW
        recommended_route_text = "Yield to emergency vehicles; use adjacent parallel streets"
        recommended_departure_before = None
        window_start = event_row.started_at
        window_end = event_row.restored_at or (event_row.started_at + timedelta(seconds=event_row.clearance_time_s))
        expires_at = window_end + timedelta(minutes=10)
        source = "sumo"

    elif origin_type == AdvisoryOriginType.INCIDENT:
        from app.models.incident import Incident
        from sqlalchemy.orm import selectinload

        res = await db.execute(
            select(Incident)
            .options(selectinload(Incident.indicators))
            .where(Incident.id == origin_id)
        )
        incident = res.scalar_one_or_none()
        # If incident does not exist or has no measured indicators, refuse honestly
        if (
            not incident
            or not getattr(incident, "indicators", None)
            or len(incident.indicators) == 0
            or not isinstance(getattr(incident, "indicators", None), list)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="insufficient data to advise: no measured incident or indicators found for this incident",
            )

        corridor_text = get_human_corridor_text(incident.link_id)
        severity = AdvisorySeverity.SEVERE if incident.confidence >= 0.75 else AdvisorySeverity.MODERATE
        headline = (
            f"Traffic alert: {corridor_text}"
            if severity == AdvisorySeverity.SEVERE
            else f"Traffic advisory: {corridor_text}"
        )
        cause_text = f"Possible traffic incident under management ({incident.indicators_fired} indicators verified)"
        delay_low, delay_high = (15, 30) if severity == AdvisorySeverity.SEVERE else (10, 20)

        recommended_route_text = f"Advise diversion around {corridor_text}; use alternate corridors"
        recommended_departure_before = None
        window_start = incident.detected_at
        window_end = incident.detected_at + timedelta(minutes=60)
        expires_at = window_end + timedelta(minutes=30)
        source = incident.source or "sumo"

    else:  # FORECAST — no real measurement pipeline exists yet,
        # so this refuses exactly as the spec requires rather than inventing numbers.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"insufficient data to advise: no measured {origin_type.value.lower()} pipeline is wired yet",
        )

    # Persist the citizen advisory
    advisory = CitizenAdvisory(
        id=uuid.uuid4(),
        origin_type=origin_type,
        origin_id=origin_id,
        headline=headline,
        corridor_text=corridor_text,
        window_start=window_start,
        window_end=window_end,
        delay_min_low=delay_low,
        delay_min_high=delay_high,
        cause_text=cause_text,
        recommended_route_text=recommended_route_text,
        recommended_departure_before=recommended_departure_before,
        severity=severity,
        published_by=user_id,
        published_at=now,
        expires_at=expires_at,
        source=source,
    )
    db.add(advisory)
    await db.flush()

    # Audit AI advisory draft creation per SN-104 & SN-105
    try:
        from app.services.audit_service import write_audit
        from app.models.audit import AuditActorType, AuditResult
        await write_audit(
            db=db,
            action="AI_ADVISORY_DRAFT",
            actor_type=AuditActorType.AI,
            actor_id=None,
            target_type="advisory",
            target_id=advisory.id,
            input_payload={"origin_type": origin_type.value, "origin_id": str(origin_id)},
            output_payload={"headline": headline, "corridor_text": corridor_text, "severity": severity.value},
            model="advisory_generator",
            model_version="1.0.0",
            confidence=0.88,
            result=AuditResult.SUCCESS,
            source=source or "advisory_service",
        )
    except Exception as audit_err:
        logger.warning(f"Failed to log AI_ADVISORY_DRAFT audit: {audit_err}")

    logger.info(f"Published citizen advisory {advisory.id} for origin {origin_id} by user {user_id}")
    return advisory
