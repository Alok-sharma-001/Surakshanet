import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.control_service.config import DEFAULT_MODE_SPLIT, ARRIVAL_PROFILE
from shared.constants import PCU_FACTORS

logger = logging.getLogger("surakshanet.event_service")

# Severity thresholds (docs/11-event-management.md §4) — fixed, documented, never tuned per demo
SEVERITY_THRESHOLDS = {
    "LOW_MAX": 15.0,        # < 15% delta travel time
    "MODERATE_MAX": 40.0,   # 15% - 40% delta travel time
                            # > 40% is SEVERE
}


def translate_demand(expected_crowd: int) -> Dict[str, Any]:
    """
    Translates attendee crowd size into expected vehicle trips using openly stated assumptions.
    Conforms to docs/11-event-management.md §3 (SN-054).

    Example with 25,000 attendees:
      two_wheeler: 25000 * 0.40 / 1.4 = 7,143
      car:         25000 * 0.25 / 2.1 = 2,976
      auto:        25000 * 0.15 / 2.5 = 1,500
      bus:         25000 * 0.15 / 35.0 = 107
      walk_other:  no vehicle trips
    """
    if expected_crowd <= 0:
        return {
            "expected_crowd": 0,
            "trips_by_mode": {
                "two_wheeler": 0,
                "car": 0,
                "auto": 0,
                "bus": 0,
                "walk_other": 0,
            },
            "total_vehicle_trips": 0,
            "total_pcu": 0.0,
            "assumptions": {
                "mode_split": DEFAULT_MODE_SPLIT,
                "arrival_profile": ARRIVAL_PROFILE,
            }
        }

    tw_trips = round(expected_crowd * DEFAULT_MODE_SPLIT["two_wheeler"]["share"] / DEFAULT_MODE_SPLIT["two_wheeler"]["occupancy"])
    car_trips = round(expected_crowd * DEFAULT_MODE_SPLIT["car"]["share"] / DEFAULT_MODE_SPLIT["car"]["occupancy"])
    auto_trips = round(expected_crowd * DEFAULT_MODE_SPLIT["auto"]["share"] / DEFAULT_MODE_SPLIT["auto"]["occupancy"])
    bus_trips = round(expected_crowd * DEFAULT_MODE_SPLIT["bus"]["share"] / DEFAULT_MODE_SPLIT["bus"]["occupancy"])

    total_trips = tw_trips + car_trips + auto_trips + bus_trips

    # PCU conversion: motorcycle 0.5, car 1.0, auto 1.0, bus 3.0
    pcu_tw = tw_trips * PCU_FACTORS.get("motorcycle", 0.5)
    pcu_car = car_trips * PCU_FACTORS.get("car", 1.0)
    pcu_auto = auto_trips * PCU_FACTORS.get("auto_rickshaw", 1.0)
    pcu_bus = bus_trips * PCU_FACTORS.get("bus", 3.0)
    total_pcu = round(pcu_tw + pcu_car + pcu_auto + pcu_bus, 1)

    return {
        "expected_crowd": expected_crowd,
        "trips_by_mode": {
            "two_wheeler": tw_trips,
            "car": car_trips,
            "auto": auto_trips,
            "bus": bus_trips,
            "walk_other": 0,
        },
        "total_vehicle_trips": total_trips,
        "total_pcu": total_pcu,
        "assumptions": {
            "mode_split": DEFAULT_MODE_SPLIT,
            "arrival_profile": ARRIVAL_PROFILE,
        }
    }


def classify_severity(delta_pct: float) -> str:
    """Classify percentage increase in travel time into documented severity bands."""
    if delta_pct < SEVERITY_THRESHOLDS["LOW_MAX"]:
        return "LOW"
    elif delta_pct <= SEVERITY_THRESHOLDS["MODERATE_MAX"]:
        return "MODERATE"
    else:
        return "SEVERE"


def compute_link_deltas(
    baseline_metrics: Dict[str, Dict[str, float]],
    event_metrics: Dict[str, Dict[str, float]]
) -> List[Dict[str, Any]]:
    """
    Computes per-link travel time differences and severity bands.
    Conforms to docs/11-event-management.md §4:
      delta_pct = (event_travel_time - baseline_travel_time) / baseline_travel_time * 100
    """
    link_deltas = []
    for link_id, b_data in baseline_metrics.items():
        if link_id not in event_metrics:
            continue
        e_data = event_metrics[link_id]

        b_tt = float(b_data.get("travel_time_s", 0.0))
        e_tt = float(e_data.get("travel_time_s", 0.0))

        if b_tt <= 0.0:
            delta_pct = 0.0
        else:
            delta_pct = round(((e_tt - b_tt) / b_tt) * 100.0, 1)

        delta_tt_s = round(e_tt - b_tt, 1)
        severity = classify_severity(delta_pct)

        link_deltas.append({
            "link_id": link_id,
            "baseline_travel_time_s": round(b_tt, 1),
            "event_travel_time_s": round(e_tt, 1),
            "delta_travel_time_s": delta_tt_s,
            "delta_pct": delta_pct,
            "severity": severity,
            "baseline_queue_m": round(float(b_data.get("queue_length_m", 0.0)), 1),
            "event_queue_m": round(float(e_data.get("queue_length_m", 0.0)), 1),
        })

    # Sort descending by delta_pct
    link_deltas.sort(key=lambda x: x["delta_pct"], reverse=True)
    return link_deltas


def compute_severity_summary(link_deltas: List[Dict[str, Any]]) -> Dict[str, int]:
    """Counts links per severity band."""
    counts = {"LOW": 0, "MODERATE": 0, "SEVERE": 0}
    for item in link_deltas:
        sev = item.get("severity", "LOW")
        if sev in counts:
            counts[sev] += 1
        else:
            counts["LOW"] += 1
    return counts


# In-memory tracking of running prediction tasks, valid only within this worker
# process. The backend runs multiple uvicorn workers (--workers 2), so a plain
# in-memory flag would be invisible to a status-check request landing on a
# different worker than the one that launched the prediction — Redis is the
# shared source of truth across workers; the in-memory dict is kept only so the
# launching worker can hold a real asyncio.Task reference for its own bookkeeping.
_running_tasks: Dict[str, Any] = {}
_PREDICTION_RUNNING_TTL_S = 600  # generous upper bound on a 300s-duration dual-world run


def _prediction_running_key(event_id: str) -> str:
    return f"event_prediction_running:{event_id}"


async def is_prediction_running(event_id: str) -> bool:
    """Returns True if a prediction simulation is actively running for event_id,

    checked via Redis so it's correct regardless of which worker handles the request.
    """
    try:
        from app.services.auth_service import get_redis_client
        redis = get_redis_client()
        return bool(await redis.exists(_prediction_running_key(str(event_id))))
    except Exception:
        # Redis unreachable: fall back to this worker's own view rather than block.
        task = _running_tasks.get(str(event_id))
        return task is not None and not task.done()


async def get_latest_prediction(event_id: Any, db) -> Optional[Any]:
    """Retrieves the most recent completed prediction for event_id from the database."""
    import uuid
    from sqlalchemy import select, desc
    from app.models.event import EventPrediction

    uid = uuid.UUID(str(event_id)) if isinstance(event_id, str) else event_id
    stmt = (
        select(EventPrediction)
        .where(EventPrediction.event_id == uid)
        .order_by(desc(EventPrediction.computed_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def execute_event_prediction(event_id: str, seed: int = 42, duration_s: int = 300):
    """Executes dual-world what-if simulation in background thread and commits prediction to DB.

    Always clears the Redis "running" flag on exit, success or failure, so a
    crashed simulation never leaves an event stuck permanently reporting
    "running" to every worker.
    """
    import uuid
    import asyncio
    from sqlalchemy import select
    from app.database import async_session_factory
    from app.models.event import Event, EventPrediction, EventStatus
    from services.control_service.ab_runner import ABRunner

    uid = uuid.UUID(str(event_id)) if isinstance(event_id, str) else event_id

    try:
        # 1. Fetch event config
        async with async_session_factory() as db:
            res = await db.execute(select(Event).where(Event.id == uid))
            event = res.scalar_one_or_none()
            if not event:
                logger.error(f"Event {event_id} not found for prediction")
                return
            crowd = event.expected_crowd or 0
            affected = event.affected_links or []
            closures = event.closure_links or []

        # 2. Run simulation via ABRunner in thread pool
        runner = ABRunner()
        prediction_result = await asyncio.to_thread(
            runner.run_event_whatif,
            event_id=str(uid),
            seed=seed,
            duration_s=duration_s,
            affected_links=affected,
            closure_links=closures,
            expected_crowd=crowd,
        )

        # 3. Persist EventPrediction and advance event status
        async with async_session_factory() as db:
            pred = EventPrediction(
                id=uuid.uuid4(),
                event_id=uid,
                seed=seed,
                baseline_metrics=prediction_result["baseline_metrics"],
                event_metrics=prediction_result["event_metrics"],
                link_deltas=prediction_result["link_deltas"],
                severity_summary=prediction_result["severity_summary"],
                alternatives=prediction_result["alternatives"],
                demand_injection=prediction_result.get("demand"),
                computed_at=datetime.utcnow(),
                source="sumo"
            )
            db.add(pred)

            evt_res = await db.execute(select(Event).where(Event.id == uid))
            evt = evt_res.scalar_one_or_none()
            if evt and evt.status == EventStatus.DRAFT:
                evt.status = EventStatus.PREDICTED

            await db.commit()
        logger.info(f"Prediction complete and saved for event {event_id}")
    except Exception:
        logger.exception(f"Event prediction failed for event {event_id}")
        raise
    finally:
        _running_tasks.pop(str(event_id), None)
        try:
            from app.services.auth_service import get_redis_client
            redis = get_redis_client()
            await redis.delete(_prediction_running_key(str(event_id)))
        except Exception:
            pass


async def launch_prediction_task(event_id: str, seed: int = 42, duration_s: int = 300) -> Any:
    """Launches an asynchronous background simulation task for event prediction.

    Marks the event as running in Redis (shared across all backend workers)
    before scheduling the task, so a concurrent request on another worker
    can't slip in and launch a second simulation for the same event.
    """
    import asyncio

    try:
        from app.services.auth_service import get_redis_client
        redis = get_redis_client()
        await redis.setex(_prediction_running_key(str(event_id)), _PREDICTION_RUNNING_TTL_S, "1")
    except Exception:
        pass

    task = asyncio.create_task(execute_event_prediction(event_id, seed, duration_s))
    _running_tasks[str(event_id)] = task
    return task
