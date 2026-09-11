"""Surakshanet ITS Native Tools for Google Antigravity SDK Agents.

Exposes core ML, forecasting, routing, and emergency preemption subsystems as
type-annotated, self-documenting functions consumable by Antigravity agents.
"""

import asyncio
import math
import uuid
import time
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


async def _run_and_dispose(coro):
    """Awaits `coro`, then disposes the shared async engine's connection pool.

    The engine's pool holds asyncpg connections bound to the event loop that
    created them. Each _run_async call below runs on a brand-new loop
    (asyncio.run()), so without this, a second tool call in the same process
    would try to reuse a connection from the first (now-closed) loop and fail
    with "Future ... attached to a different loop". Disposing forces a clean
    reconnect on the next call instead.
    """
    try:
        return await coro
    finally:
        try:
            from app.database import engine
            await engine.dispose()
        except Exception:
            pass


def _run_async(coro):
    """Runs an async coroutine from this module's synchronous tool functions.

    Antigravity agent tools are plain sync callables, but reading recent readings
    needs the app's async DB session. If the calling thread already has a running
    event loop (likely, since the agent framework itself is async), asyncio.run()
    can't be used directly there — so that case is delegated to a throwaway thread
    that owns its own loop instead.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run_and_dispose(coro))
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _run_and_dispose(coro)).result()


async def _fetch_recent_readings(junction_id: str, limit: int = 36) -> List[Dict[str, Any]]:
    """Fetches the most recent traffic_readings rows for a junction, oldest first.

    Accepts either a junction UUID or its name, mirroring the resolution pattern
    used by services/control_service/main.py::_resolve_junction.
    """
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models.traffic import TrafficReading
    from app.models.junction import Junction

    async with async_session_maker() as db:
        j_id = None
        try:
            j_id = uuid.UUID(junction_id)
        except (ValueError, AttributeError, TypeError):
            result = await db.execute(select(Junction.id).where(Junction.name.ilike(junction_id)))
            j_id = result.scalars().first()

        if j_id is None:
            return []

        result = await db.execute(
            select(TrafficReading.timestamp, TrafficReading.pcu_value)
            .where(TrafficReading.junction_id == j_id)
            .order_by(TrafficReading.timestamp.desc())
            .limit(limit)
        )
        rows = result.all()
        return [{"timestamp": ts, "pcu_value": pcu} for ts, pcu in reversed(rows)]

# Global singletons for ML engines to avoid reload overhead
_forecaster = None


def _get_forecaster():
    global _forecaster
    if _forecaster is None:
        try:
            from ml.forecasting.traffic_forecaster import TrafficForecaster
            _forecaster = TrafficForecaster()
        except Exception as e:
            logger.warning(f"Could not initialize TrafficForecaster: {e}")
    return _forecaster


def forecast_junction_traffic(junction_id: str) -> Dict[str, Any]:
    """Retrieves 15, 30, and 60-minute traffic flow forecasts and spillback probability for a junction.

    Args:
        junction_id: The UUID or identifier of the junction to forecast.

    Returns:
        A dictionary containing predicted PCU volume for 15m, 30m, and 60m horizons,
        estimated spillback risk (0.0 to 1.0), and predicted congestion level.
    """
    forecaster = _get_forecaster()
    # If model is trained and available, predict with model
    if forecaster and getattr(forecaster, "is_lstm_trained", False) and getattr(forecaster, "is_xgb_trained", False):
        try:
            recent_readings = _run_async(_fetch_recent_readings(junction_id))
            if not recent_readings:
                raise ValueError(f"No traffic_readings found for junction '{junction_id}'.")

            preds = forecaster.predict(junction_id=junction_id, recent_readings=recent_readings)
            # predict() returns {"horizons": [{"minutes": .., "predicted_pcu": ..}, ...], "spillback_risk": ..}
            by_minutes = {h["minutes"]: h["predicted_pcu"] for h in preds["horizons"]}
            p15, p30, p60 = by_minutes.get(15), by_minutes.get(30), by_minutes.get(60)
            return {
                "junction_id": junction_id,
                "forecast_15m_pcu": p15,
                "forecast_30m_pcu": p30,
                "forecast_60m_pcu": p60,
                "spillback_risk": preds["spillback_risk"],
                "trend": "INCREASING" if (p60 is not None and p15 is not None and p60 > p15) else "STABLE",
                "source": "LSTM_XGBOOST_ENSEMBLE"
            }
        except Exception as err:
            logger.warning(f"Forecaster inference error: {err}. Reporting unavailable rather than fabricating.")

    # No trained model and no way to derive a genuine estimate — report honestly,
    # matching the /ml/predict 503 contract (CLAUDE.md §5) instead of inventing numbers.
    return {
        "junction_id": junction_id,
        "forecast_15m_pcu": None,
        "forecast_30m_pcu": None,
        "forecast_60m_pcu": None,
        "spillback_risk": None,
        "trend": "UNKNOWN",
        "source": "unavailable",
        "reason": "forecasting model not trained or unavailable"
    }


async def _activate_emergency_corridor_async(
    corridor_junctions: List[str],
    vehicle_type: str,
    priority_level: int,
) -> Dict[str, Any]:
    """Requests a real emergency corridor through the same pathway POST /emergency/activate

    uses: persists a real EmergencyEvent row and publishes the real Redis command the
    live SUMO bridge (simulation/sumo_live_bridge.py) listens for. Whether any junction
    is actually pre-empted depends on that bridge genuinely being connected — this
    function only ever reports what it actually did (persisted + published a real
    request), never a fabricated "corridor cleared" claim.
    """
    import json as _json
    import redis.asyncio as aioredis
    from app.database import async_session_maker
    from app.config import get_settings
    from app.models.alert import EmergencyEvent, EmergencyPriority, EmergencyVehicleType, EmergencyStatus
    from app.services.routing_service import routing_service
    from ml.emergency.green_wave import green_wave_ctrl
    from shared.constants import REDIS_CHANNELS, DataSource
    from datetime import datetime

    settings = get_settings()
    event_uuid = uuid.uuid4()
    event_id = str(event_uuid)

    priority_map = {1: "CRITICAL", 2: "HIGH", 3: "MEDIUM"}
    priority_str = priority_map.get(priority_level, "CRITICAL")
    try:
        priority_enum = EmergencyPriority[priority_str]
    except KeyError:
        priority_enum = EmergencyPriority.CRITICAL
    try:
        vehicle_enum = EmergencyVehicleType[vehicle_type.upper()]
    except KeyError:
        vehicle_enum = EmergencyVehicleType.AMBULANCE

    # Real ETA schedule from the shared corridor controller, seeded with real
    # per-link lengths/speeds — the same computation POST /emergency/activate uses.
    result = green_wave_ctrl.activate(
        event_id=event_id,
        priority=priority_str,
        vehicle_type=vehicle_type,
        route_junction_ids=corridor_junctions,
        edge_lengths_m=routing_service.get_edge_lengths_m(corridor_junctions),
        link_speeds=routing_service.get_edge_speeds_kmh(corridor_junctions),
    )

    async with async_session_maker() as db:
        event = EmergencyEvent(
            id=event_uuid,
            priority=priority_enum,
            vehicle_type=vehicle_enum,
            route=corridor_junctions,
            route_etas=result.get("route_etas"),
            clearance_time_s=result.get("clearance_time_s"),
            status=EmergencyStatus.ACTIVE,
            started_at=datetime.utcnow(),
        )
        db.add(event)
        await db.commit()

    published = False
    try:
        redis = aioredis.from_url(settings.REDIS_URL)
        payload = {
            "type": "EMERGENCY_ACTIVATED",
            "event_id": event_id,
            "vehicle_id": f"AMB-{event_id[:4].upper()}",
            "priority": priority_str,
            "vehicle_type": vehicle_type,
            "route": corridor_junctions,
            "route_etas": result.get("route_etas"),
            "clearance_time_s": result.get("clearance_time_s"),
            "activation_policy": "rolling",
            "source": DataSource.SUMO.value,
        }
        await redis.publish(REDIS_CHANNELS["emergency"], _json.dumps(payload))
        await redis.aclose()
        published = True
    except Exception as e:
        logger.warning(f"Could not publish emergency activation to Redis: {e}")

    return {
        "status": "requested",
        "event_id": event_id,
        "corridor": corridor_junctions,
        "priority_level": priority_level,
        "vehicle_type": vehicle_type,
        "route_etas": result.get("route_etas"),
        "clearance_time_s": result.get("clearance_time_s"),
        "bridge_notified": published,
        "message": (
            "Corridor activation request persisted and published; actual pre-emption "
            "depends on a live SUMO bridge picking it up. Poll GET /emergency/{event_id}/corridor "
            "for real junction-by-junction status."
            if published else
            "Corridor activation request persisted, but the live SUMO bridge could not be "
            "notified (Redis unreachable) — no junction has actually been pre-empted."
        ),
    }


def clear_emergency_corridor(
    corridor_junctions: List[str],
    vehicle_type: str = "AMBULANCE",
    priority_level: int = 1
) -> Dict[str, Any]:
    """Requests preemption green-wave along a sequence of junctions for an approaching emergency vehicle.

    This goes through the same real pathway POST /emergency/activate uses (real
    ETA computation, a real persisted EmergencyEvent row, and a real Redis
    notification to the live SUMO bridge) — it never fabricates a "corridor
    cleared" result. Whether junctions are actually pre-empted depends on a
    live bridge being connected; check via GET /emergency/{event_id}/corridor.

    Args:
        corridor_junctions: Ordered list of junction IDs along the emergency route.
        vehicle_type: Type of vehicle, e.g. "AMBULANCE", "FIRE_ENGINE", "POLICE".
        priority_level: Priority level (1 = Highest, 2 = Medium, 3 = Low).

    Returns:
        A dictionary with the real activation request status, event_id for
        follow-up polling, and whether the live bridge was actually notified.
    """
    try:
        return _run_async(_activate_emergency_corridor_async(corridor_junctions, vehicle_type, priority_level))
    except Exception as e:
        logger.error(f"Error requesting emergency corridor activation: {e}")
        return {
            "status": "error",
            "corridor": corridor_junctions,
            "priority_level": priority_level,
            "vehicle_type": vehicle_type,
            "message": f"Corridor activation request failed: {e}",
        }


def compute_optimal_reroute(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    avoid_junction_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Computes optimal, congestion-aware detour routing between two geographic points, avoiding specified junctions.

    Runs the real A* routing engine (the same one backing /routing/* and the
    event what-if alternative-route engine) over the live-refreshed corridor
    graph — never a distance-formula estimate. Returns an honest error if no
    path exists rather than inventing a plausible-looking one.

    Args:
        origin_lat: Origin latitude coordinate.
        origin_lon: Origin longitude coordinate.
        destination_lat: Destination latitude coordinate.
        destination_lon: Destination longitude coordinate.
        avoid_junction_ids: Optional list of junction IDs with active incidents/gridlock to bypass.

    Returns:
        A dictionary containing the real measured route, travel time in minutes,
        total distance in km, and list of avoided junctions — or an honest
        "no path found" status if the routing graph has none.
    """
    from app.services.routing_service import routing_service

    avoid_set = set(avoid_junction_ids or [])
    engine = routing_service.engine

    penalties: Dict[Any, float] = {}
    if avoid_set:
        for u in engine.graph:
            for v in engine.graph[u]:
                if u in avoid_set or v in avoid_set:
                    penalties[(u, v)] = 9999.0

    baseline = engine.find_route((origin_lat, origin_lon), (destination_lat, destination_lon), profile="citizen")
    result = engine.find_route(
        (origin_lat, origin_lon), (destination_lat, destination_lon),
        profile="citizen", penalties=penalties or None,
    )

    if "error" in result or not result.get("path"):
        return {
            "status": "NO_ROUTE_FOUND",
            "origin": {"lat": origin_lat, "lon": origin_lon},
            "destination": {"lat": destination_lat, "lon": destination_lon},
            "avoided_junctions": list(avoid_set),
            "advisory": "No route could be computed between these coordinates on the current routing graph.",
        }

    actually_avoided = [j for j in avoid_set if j not in result["path"]]
    baseline_time = baseline.get("eta_minutes") if "error" not in baseline else None
    savings_min = (
        round(baseline_time - result["eta_minutes"], 1)
        if baseline_time is not None and baseline_time > result["eta_minutes"]
        else 0.0
    )

    return {
        "status": "COMPUTED",
        "origin": {"lat": origin_lat, "lon": origin_lon},
        "destination": {"lat": destination_lat, "lon": destination_lon},
        "route_text": result.get("route_text"),
        "avoided_junctions": actually_avoided,
        "total_distance_km": result["distance_km"],
        "estimated_travel_time_min": result["eta_minutes"],
        "congestion_level": result.get("congestion_level"),
        "stale": result.get("stale", False),
        "congestion_savings_min": savings_min,
        "advisory": (
            f"Route avoids {len(actually_avoided)} requested junction(s)."
            if actually_avoided else "Direct route used; no detour was necessary or possible."
        ),
        "source": "sumo",
    }


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _query_nearby_junctions_async(latitude: float, longitude: float, radius_meters: float) -> List[Dict[str, Any]]:
    from sqlalchemy import select
    from app.database import async_session_maker
    from app.models.junction import Junction

    async with async_session_maker() as db:
        result = await db.execute(select(Junction).where(Junction.is_active.is_(True)))
        junctions = result.scalars().all()

    nearby = []
    for j in junctions:
        dist = _haversine_m(latitude, longitude, j.latitude, j.longitude)
        if dist <= radius_meters:
            nearby.append({
                "id": str(j.id),
                "name": j.name,
                "lat": j.latitude,
                "lon": j.longitude,
                "distance_meters": round(dist, 1),
            })
    nearby.sort(key=lambda x: x["distance_meters"])
    return nearby


def query_nearby_junctions(
    latitude: float,
    longitude: float,
    radius_meters: float = 1500.0
) -> List[Dict[str, Any]]:
    """Performs a spatial search to locate real junctions within a radius of coordinates.

    Queries the actual `junctions` table — never a hardcoded list — so results
    reflect whatever is genuinely seeded, not a fixed set of Bangalore
    landmarks unrelated to this deployment's data.

    Args:
        latitude: Center latitude coordinate.
        longitude: Center longitude coordinate.
        radius_meters: Search radius in meters (default: 1500m).

    Returns:
        A list of real nearby junctions with their IDs, names, coordinates,
        and distance from center — empty if none are within range.
    """
    try:
        return _run_async(_query_nearby_junctions_async(latitude, longitude, radius_meters))
    except Exception as e:
        logger.warning(f"query_nearby_junctions DB lookup failed: {e}")
        return []


async def _broadcast_vms_advisory_async(
    junction_id: str, message_line_1: str, message_line_2: str, duration_minutes: int
) -> Dict[str, Any]:
    # Reuses the same in-memory VMS store /routing/vms/broadcast writes to and
    # /routing/vms/active + /routing/vms/history read from, so a message
    # published here genuinely shows up on the real VMS surfaces — never a
    # claim of "PUBLISHED" with no actual side effect.
    from app.api.routing import vms_broadcasts

    line1 = message_line_1.upper()[:20]
    line2 = message_line_2.upper()[:20]
    broadcast = {
        "id": f"vms-{int(time.time())}",
        "panel_cluster": junction_id,
        "line1": line1,
        "line2": line2,
        "priority": "HIGH",
        "timestamp": time.time(),
        "duration_minutes": duration_minutes,
        "status": "ACTIVE",
    }
    vms_broadcasts.insert(0, broadcast)
    return broadcast


def broadcast_vms_advisory(
    junction_id: str,
    message_line_1: str,
    message_line_2: str = "",
    duration_minutes: int = 15
) -> Dict[str, Any]:
    """Dispatches dynamic detour text and safety warnings to Variable Message Signs (VMS).

    Writes to the same VMS store the /routing/vms/* endpoints read from, so
    this genuinely appears on GET /routing/vms/active — it does not just
    return a "PUBLISHED" status with no real effect.

    Args:
        junction_id: Target junction ID where the VMS sign is located.
        message_line_1: Primary line of text on sign (max 20 characters).
        message_line_2: Secondary line of text on sign (max 20 characters).
        duration_minutes: Active display duration before returning to default message.

    Returns:
        A dictionary confirming the real broadcast record that was created.
    """
    try:
        broadcast = _run_async(_broadcast_vms_advisory_async(junction_id, message_line_1, message_line_2, duration_minutes))
        return {
            "status": "PUBLISHED",
            "broadcast_id": broadcast["id"],
            "junction_id": junction_id,
            "display_line_1": broadcast["line1"],
            "display_line_2": broadcast["line2"],
            "duration_minutes": duration_minutes,
        }
    except Exception as e:
        logger.error(f"Failed to publish VMS advisory: {e}")
        return {
            "status": "error",
            "junction_id": junction_id,
            "message": f"Could not publish VMS advisory: {e}",
        }


async def _get_junction_status_async(junction_id: str) -> Optional[Dict[str, Any]]:
    from sqlalchemy import select, desc
    from app.database import async_session_maker
    from app.models.junction import Junction
    from app.models.traffic import TrafficReading
    from app.models.control import ControlDecision

    async with async_session_maker() as db:
        j_id = None
        try:
            j_id = uuid.UUID(junction_id)
        except (ValueError, AttributeError, TypeError):
            result = await db.execute(select(Junction).where(Junction.name.ilike(junction_id)))
            row = result.scalars().first()
            j_id = row.id if row else None

        if j_id is None:
            return None

        junction = (await db.execute(select(Junction).where(Junction.id == j_id))).scalar_one_or_none()
        if not junction:
            return None

        latest_reading = (
            await db.execute(
                select(TrafficReading)
                .where(TrafficReading.junction_id == j_id)
                .order_by(desc(TrafficReading.timestamp))
                .limit(1)
            )
        ).scalar_one_or_none()

        latest_decision = (
            await db.execute(
                select(ControlDecision)
                .where(ControlDecision.junction_id == j_id)
                .order_by(desc(ControlDecision.timestamp))
                .limit(1)
            )
        ).scalar_one_or_none()

        return {
            "junction_id": str(junction.id),
            "junction_name": junction.name,
            "current_pcu": latest_reading.pcu_value if latest_reading else None,
            "average_speed_kmh": latest_reading.avg_speed if latest_reading else None,
            "queue_length": latest_reading.queue_length if latest_reading else None,
            "reading_source": latest_reading.source if latest_reading else None,
            "reading_timestamp": latest_reading.timestamp.isoformat() if latest_reading else None,
            "current_phase": latest_decision.applied_phase if latest_decision else None,
            "controller": latest_decision.controller if latest_decision else None,
            "decision_timestamp": latest_decision.timestamp.isoformat() if latest_decision else None,
        }


def get_junction_status(junction_id: str) -> Dict[str, Any]:
    """Retrieves real operational metrics for a junction from the database.

    Queries the most recent traffic_readings row (PCU, speed, queue) and the
    most recent control_decisions row (current phase, controller) for the
    given junction — every field is `None` rather than a plausible-looking
    number when no measurement exists yet, and results genuinely differ
    between junctions since they come from that junction's own rows.

    Args:
        junction_id: UUID or name of the junction.

    Returns:
        A dictionary with real measured PCU, speed, queue length, and signal
        state, or an honest "not found"/"no data" result.
    """
    try:
        status_data = _run_async(_get_junction_status_async(junction_id))
    except Exception as e:
        logger.warning(f"get_junction_status DB lookup failed: {e}")
        return {"junction_id": junction_id, "status": "error", "message": str(e)}

    if status_data is None:
        return {"junction_id": junction_id, "status": "not_found", "message": "No such junction in the database."}

    status_data["status"] = "ok" if status_data.get("current_pcu") is not None else "no_recent_data"
    return status_data
