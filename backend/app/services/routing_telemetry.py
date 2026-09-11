"""Feeds live junction telemetry into the routing graph (SN-041).

`RoutingEngine.update_edge_weights()` and `RoutingService.update_live_telemetry()`
were fully implemented but had zero callers — the routing graph was seeded once
at startup from the static corridor topology and never actually refreshed, so
routes never responded to real congestion. This module is that missing caller:
it caches the latest JunctionTelemetry payload per junction (cheap, updated on
every message) and refreshes the graph's edge weights from it on a slower
cadence, per docs/10-emergency-corridor.md §2's "refresh every 10s".
"""

import asyncio
import logging
import time
from typing import Any, Dict

from app.services.routing_service import routing_service, LIVE_REFRESH_INTERVAL_S

logger = logging.getLogger("surakshanet.routing_telemetry")

# junction_id -> latest telemetry payload dict.
_latest_junction_telemetry: Dict[str, Dict[str, Any]] = {}


def record_junction_telemetry(payload: Dict[str, Any]) -> None:
    """Caches the most recent telemetry payload for one junction.

    Called for every message on REDIS_CHANNELS["traffic"] — just an in-memory
    dict update. The routing graph itself is only refreshed on the slower
    cadence in `periodic_routing_refresh`, matching the spec's 10s interval.
    """
    junction_id = payload.get("junction_id")
    if not junction_id:
        return
    entry = dict(payload)
    entry["_received_at"] = time.time()
    _latest_junction_telemetry[junction_id] = entry


async def periodic_routing_refresh() -> None:
    """Refreshes the routing graph's edge weights from cached telemetry every

    LIVE_REFRESH_INTERVAL_S. Runs for the process lifetime as a background task.
    """
    while True:
        await asyncio.sleep(LIVE_REFRESH_INTERVAL_S)
        if not _latest_junction_telemetry:
            continue
        try:
            traffic_data = routing_service.build_traffic_data_from_junction_telemetry(
                _latest_junction_telemetry
            )
            if traffic_data:
                routing_service.update_live_telemetry(traffic_data)
                logger.debug(f"Routing graph refreshed from {len(traffic_data)} live edges.")
        except Exception as e:
            logger.warning(f"Routing graph live refresh failed: {e}")
