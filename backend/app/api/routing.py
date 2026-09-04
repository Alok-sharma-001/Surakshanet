import time
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from ml.routing.routing_engine import RoutingEngine

router = APIRouter(prefix="/routing", tags=["routing"])

routing_engine = RoutingEngine()

# Seed default city network nodes for Delhi & Bengaluru corridors
DEFAULT_JUNCTIONS = [
    {"id": "DEL-CP-01", "name": "Connaught Place Inner", "lat": 28.6315, "lon": 77.2167},
    {"id": "DEL-ITO-02", "name": "ITO Crossing", "lat": 28.6289, "lon": 77.2405},
    {"id": "DEL-AIIMS-03", "name": "AIIMS Flyover", "lat": 28.5672, "lon": 77.2100},
    {"id": "DEL-ASH-04", "name": "Ashram Chowk", "lat": 28.5714, "lon": 77.2588},
    {"id": "DEL-DHK-05", "name": "Dhaula Kuan", "lat": 28.5921, "lon": 77.1565},
    {"id": "DEL-LAJ-06", "name": "Lajpat Nagar", "lat": 28.5700, "lon": 77.2370},
    {"id": "BLR-MGR-01", "name": "MG Road - Brigade", "lat": 12.9756, "lon": 77.6066},
    {"id": "BLR-SLK-02", "name": "Silk Board Junction", "lat": 12.9177, "lon": 77.6238},
    {"id": "BLR-IND-03", "name": "Indiranagar 100ft", "lat": 12.9719, "lon": 77.6412},
    {"id": "BLR-KOR-04", "name": "Koramangala Sony World", "lat": 12.9352, "lon": 77.6245},
]

DEFAULT_EDGES = [
    {"from": "DEL-CP-01", "to": "DEL-ITO-02", "free_flow_speed": 45.0, "capacity": 1800},
    {"from": "DEL-ITO-02", "to": "DEL-ASH-04", "free_flow_speed": 50.0, "capacity": 2200},
    {"from": "DEL-ASH-04", "to": "DEL-LAJ-06", "free_flow_speed": 40.0, "capacity": 1600},
    {"from": "DEL-LAJ-06", "to": "DEL-AIIMS-03", "free_flow_speed": 55.0, "capacity": 2400},
    {"from": "DEL-AIIMS-03", "to": "DEL-DHK-05", "free_flow_speed": 60.0, "capacity": 2600},
    {"from": "DEL-DHK-05", "to": "DEL-CP-01", "free_flow_speed": 50.0, "capacity": 2000},
    {"from": "BLR-MGR-01", "to": "BLR-IND-03", "free_flow_speed": 35.0, "capacity": 1400},
    {"from": "BLR-IND-03", "to": "BLR-KOR-04", "free_flow_speed": 40.0, "capacity": 1500},
    {"from": "BLR-KOR-04", "to": "BLR-SLK-02", "free_flow_speed": 30.0, "capacity": 2000},
    {"from": "BLR-SLK-02", "to": "BLR-MGR-01", "free_flow_speed": 35.0, "capacity": 1800},
]

routing_engine.build_graph(DEFAULT_JUNCTIONS, DEFAULT_EDGES)

# VMS in-memory store
vms_broadcasts: List[Dict[str, Any]] = [
    {
        "id": "vms-001",
        "panel_cluster": "Cluster A (North Corr.) [4 Panels]",
        "line1": "HEAVY TRAFFIC AHEAD",
        "line2": "USE ALT ROUTE - BETA RING",
        "priority": "HIGH",
        "timestamp": time.time() - 3600,
        "status": "ACTIVE"
    },
    {
        "id": "vms-002",
        "panel_cluster": "VMS-12 (Ashram Flyover)",
        "line1": "ACCIDENT CLEARED",
        "line2": "RESUME NORMAL SPEED",
        "priority": "NORMAL",
        "timestamp": time.time() - 7200,
        "status": "EXPIRED"
    }
]

class RouteRequest(BaseModel):
    origin_lat: Optional[float] = None
    origin_lon: Optional[float] = None
    dest_lat: Optional[float] = None
    dest_lon: Optional[float] = None
    origin: Optional[Dict[str, float]] = None
    destination: Optional[Dict[str, float]] = None

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
    """Compute optimal route between coordinates using A* search."""
    origin, destination = data.get_coords()
    
    result = routing_engine.find_route(origin, destination)
    if "error" in result:
        # Fallback to direct path with distance estimate
        dist_km = routing_engine._haversine(origin[0], origin[1], destination[0], destination[1])
        result = {
            "origin": [origin[0], origin[1]],
            "destination": [destination[0], destination[1]],
            "path": [[origin[0], origin[1]], [destination[0], destination[1]]],
            "estimated_time_min": round((dist_km / 35.0) * 60, 1),
            "distance_km": round(dist_km, 2),
            "congestion_level": "MODERATE"
        }
    
    result["distance"] = result.get("distance_km", 0.0)
    result["duration"] = result.get("estimated_time_min", result.get("eta_minutes", 0.0))
    return result

@router.post("/alternatives")
async def compute_alternatives(data: RouteRequest):
    """Compute primary and alternative routes for dynamic diversion."""
    origin, destination = data.get_coords()
    
    routes = routing_engine.find_alternatives(origin, destination, num_routes=2)
    for r in routes:
        r["distance"] = r.get("distance_km", 0.0)
        r["duration"] = r.get("estimated_time_min", r.get("eta_minutes", 0.0))
    return routes

@router.get("/congestion")
async def get_congestion():
    """Get current network edge congestion levels."""
    edges_data = []
    for u in routing_engine.graph:
        for v, data in routing_engine.graph[u].items():
            edges_data.append({
                "from": u,
                "to": v,
                "distance_km": round(data["distance"], 2),
                "current_speed_kmh": round(data.get("current_speed", data["speed"]), 1),
                "congestion_level": routing_engine.get_congestion_level(
                    data.get("current_speed", data["speed"]), data["speed"]
                )
            })
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
