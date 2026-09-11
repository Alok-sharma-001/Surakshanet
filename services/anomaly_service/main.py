"""SurakshaNet Anomaly Detection Service (SN-085, SN-090)
======================================================
Consumes canonical traffic telemetry from Redis (REDIS_CHANNELS["traffic"]),
maintains rolling per-link baselines, evaluates the 5 anomaly indicators,
applies the combination rule with one-open-incident-per-link deduplication,
creates UNVERIFIED Possible Incident records, and auto-resolves after 5 minutes
of all-clear (logged as auto_cleared, never silently deleted).
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in [_repo_root, os.path.join(_repo_root, "backend")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sqlalchemy import select, update, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
import redis.asyncio as aioredis

from app.config import get_settings
from app.models.incident import (
    Incident,
    IncidentIndicator,
    IncidentType,
    IncidentStatus,
    IncidentIndicatorType,
)
from app.models.audit import AuditActorType, AuditResult
from app.services.audit_service import write_audit
from shared.constants import REDIS_CHANNELS, DataSource
from shared.corridor_topology import edge_for_telemetry_approach, upstream_edge_for_sumo_id
from services.anomaly_service.indicators import (
    evaluate_speed_collapse,
    evaluate_stationary_vehicle,
    evaluate_occupancy_spike,
    evaluate_flow_drop,
    evaluate_queue_anomaly,
    IndicatorResult,
)
from services.anomaly_service.rules import (
    evaluate_anomaly_combination,
    AnomalyEvaluation,
)

logger = logging.getLogger("surakshanet.anomaly_service")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# 5 minutes (300 s) of all-clear auto-resolves an unconfirmed incident (SN-090)
AUTO_RESOLVE_CLEAR_SECONDS = 300.0


class LinkTelemetryBuffer:
    """Maintains a rolling 15-minute history of telemetry for a single link

    to compute rolling measured baselines rather than typed-in assumptions.
    """

    def __init__(self, link_id: str, max_window_s: float = 900.0):
        self.link_id = link_id
        self.max_window_s = max_window_s  # 15 minutes
        self.history: deque = deque()  # (timestamp, speed_kmh, occupancy, flow, queue_length)

    def add_sample(
        self,
        speed_kmh: Optional[float],
        occupancy: float,
        flow: float,
        queue_length: float,
        timestamp: Optional[float] = None,
    ):
        t = timestamp or time.time()
        s_val = float(speed_kmh) if speed_kmh is not None else None
        self.history.append((t, s_val, float(occupancy), float(flow), float(queue_length)))
        self._prune(t)

    def _prune(self, current_time: float):
        cutoff = current_time - self.max_window_s
        while self.history and self.history[0][0] < cutoff:
            self.history.popleft()

    def get_baseline_speed(self) -> float:
        speeds = [s[1] for s in self.history if s[1] is not None]
        if not speeds:
            return 50.0  # Default free flow fallback until samples accumulate
        return sum(speeds) / len(speeds)

    def get_baseline_occupancy(self) -> float:
        if not self.history:
            return 0.20
        occs = [s[2] for s in self.history]
        return sum(occs) / len(occs)

    def get_last_flow(self) -> Optional[float]:
        """Most recently recorded real flow sample for this link, or None if
        nothing has been recorded yet."""
        if not self.history:
            return None
        return self.history[-1][3]

    def get_queue_growth_rate(self, window_s: float = 90.0) -> float:
        """Computes rate of queue growth (vehicles/min) over recent window."""
        if len(self.history) < 2:
            return 0.0
        now = self.history[-1][0]
        cutoff = now - window_s
        window_samples = [s for s in self.history if s[0] >= cutoff]
        if len(window_samples) < 2:
            return 0.0
        dt_min = (window_samples[-1][0] - window_samples[0][0]) / 60.0
        if dt_min <= 0.05:
            return 0.0
        d_queue = window_samples[-1][4] - window_samples[0][4]
        return max(0.0, d_queue / dt_min)


class AnomalyDetector:
    """Autonomous Anomaly Detector managing rolling telemetry buffers,

    indicator evaluations, open incident lifecycle, and Redis/DB persistence.
    """

    def __init__(self, session_factory=None, redis_client=None):
        self.session_factory = session_factory
        self.redis = redis_client
        self.link_buffers: Dict[str, LinkTelemetryBuffer] = {}
        # Tracks open incidents per link: link_id -> {"incident_id": UUID, "first_detected": ts, "clear_start": ts}
        self.open_incidents: Dict[str, Dict[str, Any]] = {}
        # Tracks vehicle stationary duration: link_id -> max_stationary_s
        self.stationary_trackers: Dict[str, float] = {}

    def get_or_create_buffer(self, link_id: str) -> LinkTelemetryBuffer:
        if link_id not in self.link_buffers:
            self.link_buffers[link_id] = LinkTelemetryBuffer(link_id)
        return self.link_buffers[link_id]

    def record_telemetry(
        self,
        link_id: str,
        speed_kmh: Optional[float],
        occupancy: float,
        flow: float,
        queue_length: float,
        timestamp: Optional[float] = None,
        stationary_s: float = 0.0,
    ):
        buf = self.get_or_create_buffer(link_id)
        buf.add_sample(speed_kmh, occupancy, flow, queue_length, timestamp)
        if stationary_s > 0.0:
            self.stationary_trackers[link_id] = stationary_s
        elif link_id in self.stationary_trackers:
            # Decay stationary tracker if vehicles are moving
            if speed_kmh is not None and speed_kmh > 15.0:
                self.stationary_trackers[link_id] = 0.0

    def evaluate_link(
        self,
        link_id: str,
        current_speed_kmh: Optional[float],
        current_occupancy: float,
        current_flow: float,
        upstream_flow: float,
        controlling_signal_red: bool = False,
        is_normal_red_phase: bool = False,
        in_queue_context: bool = False,
        tracking_available: bool = True,
    ) -> Tuple[AnomalyEvaluation, List[IndicatorResult]]:
        """Evaluates all 5 indicators for a single link."""
        buf = self.get_or_create_buffer(link_id)
        baseline_speed = buf.get_baseline_speed()
        baseline_occupancy = buf.get_baseline_occupancy()
        queue_growth = buf.get_queue_growth_rate(window_s=90.0)
        max_stationary = self.stationary_trackers.get(link_id, 0.0)

        # 1. Speed Collapse (SN-086)
        res_speed = evaluate_speed_collapse(
            mean_speed_kmh=current_speed_kmh,
            baseline_speed_kmh=baseline_speed,
            controlling_signal_red=controlling_signal_red,
            is_normal_red_phase=is_normal_red_phase,
        )

        # 2. Stationary Vehicle (SN-087)
        res_stat = evaluate_stationary_vehicle(
            max_stationary_s=max_stationary,
            in_queue_context=in_queue_context,
            controlling_signal_red=controlling_signal_red,
            data_source_available=tracking_available,
        )

        # 3. Occupancy Spike (SN-088)
        res_occ = evaluate_occupancy_spike(
            measured_occupancy=current_occupancy,
            baseline_occupancy=baseline_occupancy,
        )

        # 4. Flow Drop (SN-088)
        res_flow = evaluate_flow_drop(
            downstream_throughput=current_flow,
            upstream_throughput=upstream_flow,
        )

        # 5. Queue Anomaly (SN-088)
        res_queue = evaluate_queue_anomaly(
            queue_growth_rate=queue_growth,
            normal_growth_rate=1.0,  # Expected normal growth in free-flowing traffic
        )

        indicators = [res_speed, res_stat, res_occ, res_flow, res_queue]
        evaluation = evaluate_anomaly_combination(indicators)
        return evaluation, indicators

    async def process_and_persist(
        self,
        db: AsyncSession,
        link_id: str,
        evaluation: AnomalyEvaluation,
        junction_id: Optional[str] = None,
        source: str = "sumo",
        evidence_ref: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Optional[Incident]:
        """Deduplicates open incidents per link (SN-090).

        Creates new incident if none open; updates existing if open;
        auto-resolves if cleared for 5 minutes (SN-090).
        """
        current_dt = now or datetime.utcnow()
        current_time_epoch = time.time()

        if evaluation.should_raise:
            # Anomaly condition met!
            # If not in in-memory open_incidents, check DB first to prevent duplicates after restart
            if link_id not in self.open_incidents:
                db_res = await db.execute(
                    select(Incident)
                    .options(selectinload(Incident.indicators))
                    .where(
                        Incident.link_id == link_id,
                        Incident.status.in_([
                            IncidentStatus.UNVERIFIED,
                            IncidentStatus.DETECTED,
                            IncidentStatus.UNDER_REVIEW,
                            IncidentStatus.CONFIRMED,
                            IncidentStatus.RESPONDING,
                        ]),
                    )
                    .order_by(desc(Incident.detected_at))
                    .limit(1)
                )
                existing_open = db_res.scalar_one_or_none()
                if existing_open:
                    self.open_incidents[link_id] = {
                        "incident_id": existing_open.id,
                        "first_detected": (
                            existing_open.detected_at.timestamp()
                            if existing_open.detected_at
                            else current_time_epoch
                        ),
                        "clear_start": None,
                    }

            # Reset clear timer if it was running
            if link_id in self.open_incidents:
                self.open_incidents[link_id]["clear_start"] = None
                incident_id = self.open_incidents[link_id]["incident_id"]

                # Fetch existing incident to update
                res = await db.execute(
                    select(Incident)
                    .options(selectinload(Incident.indicators))
                    .where(Incident.id == incident_id)
                )
                existing = res.scalar_one_or_none()
                if existing and existing.status in (
                    IncidentStatus.UNVERIFIED,
                    IncidentStatus.DETECTED,
                    IncidentStatus.UNDER_REVIEW,
                    IncidentStatus.CONFIRMED,
                    IncidentStatus.RESPONDING,
                ):
                    existing.confidence = evaluation.confidence
                    existing.indicators_fired = evaluation.indicators_fired
                    existing.indicators_total = evaluation.indicators_total
                    existing.updated_at = current_dt

                    # Update indicators
                    existing_ind_map = {ind.indicator.value: ind for ind in existing.indicators}
                    for f in evaluation.fired_indicators:
                        if f.indicator in existing_ind_map:
                            existing_ind_map[f.indicator].measured_value = f.measured_value
                            existing_ind_map[f.indicator].threshold = f.threshold
                            existing_ind_map[f.indicator].fired_at = current_dt
                        else:
                            ind_type = IncidentIndicatorType(f.indicator)
                            new_ind = IncidentIndicator(
                                incident=existing,
                                indicator=ind_type,
                                measured_value=f.measured_value,
                                threshold=f.threshold,
                                fired_at=current_dt,
                            )
                            db.add(new_ind)

                    await db.flush()
                    await self._publish_incident_event(existing, "incident_updated")
                    return existing

            # If no open incident exists for this link, create new one
            new_incident = Incident(
                incident_type=IncidentType.POSSIBLE_INCIDENT,
                status=IncidentStatus.UNVERIFIED,
                link_id=link_id,
                junction_id=junction_id,
                detected_at=current_dt,
                confidence=evaluation.confidence,
                indicators_fired=evaluation.indicators_fired,
                indicators_total=evaluation.indicators_total,
                # No fabricated path guess: nothing in this pipeline actually
                # captures or stores a blurred snapshot yet (the vision
                # worker's PrivacyBlurrer is never invoked — see the Phase 5
                # audit trail). A real evidence_ref only exists when the
                # caller genuinely has one; otherwise it stays null rather
                # than pointing at a file that will never exist on disk.
                evidence_ref=evidence_ref,
                source=source,
                note="Possible incident. Unverified — operator review required.",
                created_at=current_dt,
                updated_at=current_dt,
            )
            # Add fired indicators (write-time check requires >= 1 indicator row)
            for f in evaluation.fired_indicators:
                ind_type = IncidentIndicatorType(f.indicator)
                new_incident.indicators.append(
                    IncidentIndicator(
                        indicator=ind_type,
                        measured_value=f.measured_value,
                        threshold=f.threshold,
                        fired_at=current_dt,
                    )
                )

            db.add(new_incident)
            await db.flush()

            # Audit AI incident detection per SN-104 & SN-105
            try:
                await write_audit(
                    db=db,
                    action="AI_INCIDENT_DETECT",
                    actor_type=AuditActorType.AI,
                    actor_id=None,
                    target_type="incident",
                    target_id=new_incident.id,
                    input_payload={
                        "link_id": link_id,
                        "indicators_fired": evaluation.indicators_fired,
                        "indicators_total": evaluation.indicators_total,
                        "fired_indicators": [
                            {"indicator": f.indicator, "measured_value": f.measured_value, "threshold": f.threshold}
                            for f in evaluation.fired_indicators
                        ],
                    },
                    output_payload={"incident_id": str(new_incident.id), "status": "UNVERIFIED"},
                    model="anomaly_detector",
                    model_version="1.0.0",
                    confidence=float(evaluation.confidence),
                    result=AuditResult.SUCCESS,
                    source=source or "anomaly_service",
                )
            except Exception as audit_err:
                logger.error(f"Failed to log AI_INCIDENT_DETECT audit: {audit_err}")

            self.open_incidents[link_id] = {
                "incident_id": new_incident.id,
                "first_detected": current_time_epoch,
                "clear_start": None,
            }

            logger.info(
                f"[SN-090] Raised new incident {new_incident.id} on link {link_id} "
                f"({evaluation.indicators_fired}/{evaluation.indicators_total} indicators, "
                f"confidence={evaluation.confidence})"
            )
            await self._publish_incident_event(new_incident, "incident_created")
            return new_incident

        else:
            # Anomaly cleared or condition not met
            if link_id in self.open_incidents:
                info = self.open_incidents[link_id]
                if info["clear_start"] is None:
                    info["clear_start"] = current_time_epoch
                else:
                    elapsed_clear = current_time_epoch - info["clear_start"]
                    if elapsed_clear >= AUTO_RESOLVE_CLEAR_SECONDS:
                        # Auto-resolve after 5 minutes of all-clear (SN-090)
                        incident_id = info["incident_id"]
                        res = await db.execute(
                            select(Incident).where(Incident.id == incident_id)
                        )
                        inc = res.scalar_one_or_none()
                        if inc and inc.status in (
                            IncidentStatus.UNVERIFIED,
                            IncidentStatus.DETECTED,
                            IncidentStatus.UNDER_REVIEW,
                        ):
                            inc.status = IncidentStatus.RESOLVED
                            inc.resolution = "auto_cleared"
                            inc.updated_at = current_dt
                            await db.flush()

                            await write_audit(
                                db=db,
                                action="INCIDENT_AUTO_RESOLVE",
                                actor_type=AuditActorType.SYSTEM,
                                target_type="incident",
                                target_id=inc.id,
                                input_payload={"clear_duration_s": elapsed_clear},
                                output_payload={"resolution": "auto_cleared"},
                                result=AuditResult.SUCCESS,
                                source="anomaly_service",
                            )

                            logger.info(
                                f"[SN-090] Auto-resolved incident {inc.id} on link {link_id} "
                                f"after {elapsed_clear:.0f}s of all-clear."
                            )
                            await self._publish_incident_event(inc, "incident_auto_cleared")
                            del self.open_incidents[link_id]
                        elif inc and inc.status in (
                            IncidentStatus.RESOLVED,
                            IncidentStatus.DISMISSED,
                            IncidentStatus.CLOSED,
                        ):
                            del self.open_incidents[link_id]
                        else:
                            # Confirmed or responding incident requires human operator action to resolve
                            info["clear_start"] = None

        return None

    async def _publish_incident_event(self, incident: Incident, event_type: str):
        if not self.redis:
            return
        try:
            payload = {
                "type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "source": incident.source,
                "payload": {
                    "id": str(incident.id),
                    "incident_type": incident.incident_type.value,
                    "status": incident.status.value,
                    "link_id": incident.link_id,
                    "junction_id": incident.junction_id,
                    "detected_at": incident.detected_at.isoformat(),
                    "confidence": incident.confidence,
                    "indicators_fired": incident.indicators_fired,
                    "indicators_total": incident.indicators_total,
                    "indicators": [
                        {
                            "indicator": ind.indicator.value,
                            "measured_value": ind.measured_value,
                            "threshold": ind.threshold,
                        }
                        for ind in (incident.indicators or [])
                    ],
                    "evidence_ref": incident.evidence_ref,
                    "note": incident.note,
                    "resolution": incident.resolution,
                    "confirmed_by": str(incident.confirmed_by) if incident.confirmed_by else None,
                    "warning_published_at": incident.warning_published_at.isoformat() if incident.warning_published_at else None,
                },
            }
            channel = REDIS_CHANNELS["incidents"]
            await self.redis.publish(channel, json.dumps(payload))
        except Exception as e:
            logger.warning(f"Failed to publish incident event to Redis: {e}")


async def run_anomaly_service():
    """Main execution loop for the standalone anomaly service process."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    detector = AnomalyDetector(session_factory=session_factory, redis_client=redis_client)
    pubsub = redis_client.pubsub()
    traffic_channel = REDIS_CHANNELS["traffic"]
    await pubsub.subscribe(traffic_channel)
    logger.info(f"Anomaly service subscribed to Redis channel '{traffic_channel}'")

    try:
        async for message in pubsub.listen():
            if not message or message.get("type") != "message":
                continue
            try:
                data = json.loads(message.get("data", "{}"))
                # Expecting canonical telemetry payload
                junction_id = data.get("junction_id")
                approaches = data.get("approaches", [])
                source = data.get("source", "sumo")

                async with session_factory() as db:
                    for app in approaches:
                        direction = app.get("direction", "N")
                        corridor_edge = edge_for_telemetry_approach(junction_id, direction) if junction_id else None
                        link_id = app.get("link_id") or corridor_edge or f"{junction_id}_{direction}"

                        raw_speed = app.get("mean_speed_kmh")
                        speed = float(raw_speed) if raw_speed is not None else None
                        occupancy = float(app.get("occupancy") or 0.0)
                        flow = float(app.get("pcu") or 0.0)
                        queue = float(app.get("queue_length_m") or 0.0) / 7.0  # Approx vehicles

                        # Real upstream link's most recently measured flow
                        # (SN-088) — never derived from this same sample.
                        # 0.0 (honest "no data yet") until that link's own
                        # telemetry has accumulated at least one reading;
                        # evaluate_flow_drop already treats <= 0.0 upstream
                        # as unavailable rather than firing on it.
                        upstream = 0.0
                        upstream_edge_id = upstream_edge_for_sumo_id(link_id)
                        if upstream_edge_id:
                            upstream_buf = detector.link_buffers.get(upstream_edge_id)
                            if upstream_buf:
                                upstream = upstream_buf.get_last_flow() or 0.0
                        tracking_available = source in ("sumo", "vision")

                        detector.record_telemetry(
                            link_id=link_id,
                            speed_kmh=speed,
                            occupancy=occupancy,
                            flow=flow,
                            queue_length=queue,
                        )

                        evaluation, _ = detector.evaluate_link(
                            link_id=link_id,
                            current_speed_kmh=speed,
                            current_occupancy=occupancy,
                            current_flow=flow,
                            upstream_flow=upstream,
                            controlling_signal_red=False,
                            tracking_available=tracking_available,
                        )

                        await detector.process_and_persist(
                            db=db,
                            link_id=link_id,
                            evaluation=evaluation,
                            junction_id=junction_id,
                            source=source,
                        )
                    await db.commit()

            except Exception as e:
                logger.error(f"Error processing telemetry message: {e}", exc_info=True)

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(traffic_channel)
        await redis_client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(run_anomaly_service())
    except KeyboardInterrupt:
        logger.info("Anomaly service terminated by user.")
