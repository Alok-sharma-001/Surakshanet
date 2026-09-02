from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any

class RouteRequest(BaseModel):
    origin_lat: float
    origin_lon: float
    dest_lat: float
    dest_lon: float

router = APIRouter(prefix="/routing", tags=["routing"])

from ...ml.routing.routing_engine import RoutingEngine
# Initialize a global instance for the API to use
routing_engine = RoutingEngine()

@router.post("/route")
async def compute_route(data: RouteRequest):
    """Compute the best route."""
    origin = (data.origin_lat, data.origin_lon)
    destination = (data.dest_lat, data.dest_lon)
    
    result = routing_engine.find_route(origin, destination)
    if "error" in result:
        return {"status": "error", "message": result["error"]}
        
    return result

@router.post("/alternatives")
async def compute_alternatives(data: RouteRequest):
    """Compute alternative routes."""
    origin = (data.origin_lat, data.origin_lon)
    destination = (data.dest_lat, data.dest_lon)
    
    routes = routing_engine.find_alternatives(origin, destination, num_routes=3)
    return {"routes": routes}

@router.get("/congestion")
async def get_congestion():
    """Get current congestion map data."""
    if not routing_engine.graph:
        return {"edges": []}
        
    edges_data = []
    for u in routing_engine.graph:
        for v, data in routing_engine.graph[u].items():
            edges_data.append({
                "from": u,
                "to": v,
                "congestion_level": routing_engine.get_congestion_level(data.get("current_speed", data["speed"]), data["speed"])
            })
            
    return {"edges": edges_data}
