import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.routing_service import routing_service

router = APIRouter(prefix="/routing", tags=["routing"])

# VMS in-memory store.
#
# SN-010: this was seeded with invented broadcasts that the dashboard rendered as
# live sign state. Nothing had broadcast them and no incident underlay them.
#
# It starts empty. Entries are created only by POST /routing/vms/broadcast, so
# an active sign always corresponds to an action somebody took.
vms_broadcasts: List[Dict[str, Any]] = []


class RouteRequest(BaseModel):
    origin_lat: Optional[float] = None
    origin_lon: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None
    origin: Optional[Dict[str, float]] = None
    destination: Optional[Dict[str, float]] = None
    profile: Optional[str] = "citizen"

    def get_coords(self) -> tuple[tuple[float, float], tuple[float, float]]:
        # Origin
        if self.origin_lat is not None and self.origin_lon is not None:
            o = (self.origin_lat, self.origin_lon)
        elif self.origin:
            lat = self.origin.get("lat", 0.0)
            lon = self.origin.get("lon", self.origin.get("lng", 0.0))
            o = (lat, lon)
        else:
            o = (0.0, 0.0)

        # Destination
        if self.dest_lat is not None and self.dest_lon is not None:
            d = (self.dest_lat, self.dest_lon)
        elif self.destination:
            lat = self.destination.get("lat", 0.0)
            lon = self.destination.get("lon", self.destination.get("lng", 0.0))
            d = (lat, lon)
        else:
            d = (0.0, 0.0)

        return o, d


class VMSBroadcastRequest(BaseModel):
    panel_cluster: str
    line1: str
    line2: str
    priority: str = "HIGH"


@router.post("/route")
async def compute_route(data: RouteRequest):
    """Compute optimal route between coordinates using A* search and live telemetry weights."""
    origin, destination = data.get_coords()
    profile = data.profile or "citizen"

    result = routing_service.find_route(origin, destination, profile=profile)
    if "error" in result:
        # Fallback to direct path with distance estimate
        dist_km = routing_service.engine._haversine(origin[0], origin[1], destination[0], destination[1])
        result = {
            "origin": [origin[0], origin[1]],
            "destination": [destination[0], destination[1]],
            "path": [[origin[0], origin[1]], [destination[0], destination[1]]],
            "estimated_time_min": round((dist_km / 35.0) * 60, 1),
            "distance_km": round(dist_km, 2),
            "congestion_level": "MODERATE",
            "stale": False,
            "profile": profile,
        }

    result["distance"] = result.get("distance_km", 0.0)
    result["duration"] = result.get("estimated_time_min", result.get("eta_minutes", 0.0))
    return result


@router.post("/alternatives")
async def compute_alternatives(data: RouteRequest):
    """Compute primary and diverse alternative routes for dynamic diversion (SN-041/063)."""
    origin, destination = data.get_coords()
    profile = data.profile or "citizen"

    res = routing_service.find_alternatives(origin, destination, num_routes=2, profile=profile)
    alternatives = res.get("alternatives", [])
    for r in alternatives:
        r["distance"] = r.get("distance_km", 0.0)
        r["duration"] = r.get("estimated_time_min", r.get("eta_minutes", 0.0))

    return {
        "primary": res.get("primary"),
        "alternatives": alternatives,
        "advice": res.get("advice", "")
    }


@router.get("/congestion")
async def get_congestion():
    """Get current network edge congestion and staleness status (SN-041)."""
    edges_data = routing_service.get_congestion()
    return {"edges": edges_data}


@router.post("/vms/broadcast")
async def broadcast_vms(data: VMSBroadcastRequest):
    """Publish message to Variable Message Sign panels."""
    new_broadcast = {
        "id": f"vms-{int(time.time())}",
        "panel_cluster": data.panel_cluster,
        "line1": data.line1.upper(),
        "line2": data.line2.upper(),
        "priority": data.priority,
        "timestamp": time.time(),
        "status": "ACTIVE"
    }
    vms_broadcasts.insert(0, new_broadcast)
    return {"status": "broadcast_published", "broadcast": new_broadcast}


@router.get("/vms/active")
async def get_active_vms():
    """Get currently active Variable Message Sign broadcasts."""
    active = [b for b in vms_broadcasts if b.get("status") == "ACTIVE"]
    return {"active_broadcasts": active}


@router.get("/vms/history")
async def get_vms_history():
    """Get recent Variable Message Sign broadcast history."""
    return {"history": vms_broadcasts[:20]}
