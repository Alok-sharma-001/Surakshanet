"""Caches the live SUMO bridge's most recent SIMULATION_TICK and reports an
honest liveness status for it (the Simulation page's read path).

simulation/sumo_live_bridge.py is the only process with a real TraCI
connection to the corridor simulation. It already publishes a per-step
SIMULATION_TICK on REDIS_CHANNELS["simulation"], and main.py's
redis_pubsub_bridge() already forwards that to the "simulation" WebSocket
room — this module is the missing read-side cache, structured exactly like
app/services/routing_telemetry.py does for the traffic channel, so a REST
caller can ask "what did the bridge last report, and how long ago?"

Liveness is a real measurement, never an assumption:
  - tick_age_s: time.monotonic() since THIS process actually received a tick.
    Immune to host clock jumps, and impossible for a dying bridge to leave
    behind — Redis pub/sub delivers nothing at all once the publisher stops.
  - heartbeat_age_s: an independent cross-check against the bridge's own
    Redis TTL key (simulation:bridge:heartbeat), which self-expires under
    SIGKILL/SIGTERM/crash because the bridge's stop() writes nothing to
    Redis on shutdown.
  - sumo:step is deliberately never used here: it is a plain SET with no
    TTL, nothing in this repo ever deletes it, and it was observed live
    frozen at a stale value long after the bridge had stopped — using it
    alone would reproduce the exact "looks connected but isn't" bug this
    module exists to fix.
"""
import time
import logging
from typing import Any, Dict, Optional

from shared.constants import BRIDGE_TICK_STALE_AFTER_S

logger = logging.getLogger("surakshanet.bridge_observer")

_latest_tick: Optional[Dict[str, Any]] = None


def record_bridge_tick(payload: Dict[str, Any]) -> None:
    """Caches the bridge's latest SIMULATION_TICK. Called on every message on
    REDIS_CHANNELS["simulation"] — the "simulation" room is shared with the
    API's own private-sandbox broadcasts, so the type discriminator matters:
    without it, a sandbox message would be cached as if it were the bridge."""
    global _latest_tick
    if payload.get("type") != "SIMULATION_TICK":
        return
    entry = dict(payload)
    entry["_received_monotonic"] = time.monotonic()
    entry["_received_wall"] = time.time()
    _latest_tick = entry


async def _get_heartbeat_age_s() -> Optional[float]:
    """Independent cross-check: how old is the bridge's own Redis heartbeat
    key, or None if it is absent. Absent means "not proven alive" — the
    heartbeat is written only in the redis-py branch of the bridge's publish
    path, so a bridge running on the raw-socket fallback publishes real
    ticks with no heartbeat at all. It never means "proven dead" on its own."""
    try:
        from app.config import get_settings
        import redis.asyncio as aioredis
        settings = get_settings()
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        raw = await r.get("simulation:bridge:heartbeat")
        await r.aclose()
        if raw is None:
            return None
        return max(0.0, time.time() - float(raw))
    except Exception as e:
        logger.debug(f"Bridge heartbeat read failed: {e}")
        return None


async def observe_bridge() -> Dict[str, Any]:
    """Builds GET /simulation/live's response. Every value field is the real
    measurement or None — never inferred from the other signal, never a
    last-good value held past its actual age."""
    heartbeat_age_s = await _get_heartbeat_age_s()
    tick = _latest_tick

    if tick is None:
        if heartbeat_age_s is not None:
            status, reason = "connecting", (
                f"bridge heartbeat is {heartbeat_age_s:.1f}s old but this "
                "worker has not received a tick yet"
            )
        else:
            status, reason = "unavailable", (
                "no tick received and no bridge heartbeat: the live SUMO "
                "bridge is not publishing"
            )
        return _response(status, reason, tick_age_s=None, heartbeat_age_s=heartbeat_age_s)

    tick_age_s = time.monotonic() - tick["_received_monotonic"]

    if tick_age_s <= BRIDGE_TICK_STALE_AFTER_S:
        return _response(
            "live", None, tick_age_s=tick_age_s, heartbeat_age_s=heartbeat_age_s, tick=tick
        )

    if heartbeat_age_s is not None:
        status, reason = "stale", (
            f"bridge heartbeat fresh but no tick for {tick_age_s:.1f}s"
        )
    else:
        status, reason = "unavailable", (
            f"last tick {tick_age_s:.1f}s ago; bridge heartbeat gone"
        )
    return _response(
        status, reason, tick_age_s=tick_age_s, heartbeat_age_s=heartbeat_age_s,
        last_step=tick.get("step"), last_tick_age_s=tick_age_s,
    )


def _response(
    status: str,
    reason: Optional[str],
    tick_age_s: Optional[float],
    heartbeat_age_s: Optional[float],
    tick: Optional[Dict[str, Any]] = None,
    last_step: Optional[int] = None,
    last_tick_age_s: Optional[float] = None,
) -> Dict[str, Any]:
    live = tick if status == "live" else {}
    return {
        "status": status,
        "reason": reason,
        "source": live.get("source") if status == "live" else None,
        "tick_age_s": round(tick_age_s, 2) if tick_age_s is not None else None,
        "heartbeat_age_s": round(heartbeat_age_s, 2) if heartbeat_age_s is not None else None,
        "step": live.get("step"),
        "sim_time_s": live.get("sim_time_s"),
        "total_vehicles": live.get("total_vehicles"),
        "avg_speed": live.get("avg_speed"),
        "mean_accumulated_wait_s": live.get("mean_accumulated_wait_s"),
        "throughput": live.get("throughput"),
        "network_los": live.get("network_los"),
        "queue_length": live.get("queue_length"),
        "config": live.get("config"),
        "seed": live.get("seed"),
        # "RUNNING" | "PAUSED" | None (older bridge build / not live). A
        # paused bridge is still status: "live" — it keeps publishing ticks
        # at the normal cadence — so run_state is what distinguishes "live
        # and stepping" from "live and paused" for the UI's Play/Pause state.
        "run_state": live.get("run_state"),
        # Explicitly historical — only populated on a stale/unavailable
        # response that has previously seen a tick. Never rendered as a
        # current reading by the frontend.
        "last_step": last_step,
        "last_tick_age_s": round(last_tick_age_s, 2) if last_tick_age_s is not None else None,
    }
