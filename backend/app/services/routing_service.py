import logging
import time
from typing import List, Dict, Tuple, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ml.routing.routing_engine import RoutingEngine
from app.models.junction import Junction
from app.models.network import NetworkLink
from shared.corridor_topology import CORRIDOR_JUNCTIONS, CORRIDOR_EDGES, telemetry_approach_for_edge

logger = logging.getLogger("surakshanet.routing_service")

# SN-041: refresh the routing graph from live telemetry on this cadence.
LIVE_REFRESH_INTERVAL_S = 10.0


class RoutingService:
    """Singleton service managing the live ITS routing graph, refreshing weights from

    telemetry and serving route / alternative route queries.
    """

    _instance: Optional["RoutingService"] = None

    def __init__(self):
        self.engine = RoutingEngine()
        self.is_initialized = False
        # Initialize default corridor network immediately
        self.engine.build_graph(CORRIDOR_JUNCTIONS, CORRIDOR_EDGES)
        self.is_initialized = True

    @classmethod
    def get_instance(cls) -> "RoutingService":
        if cls._instance is None:
            cls._instance = RoutingService()
        return cls._instance

    async def initialize_from_db(self, db: AsyncSession):
        """Initializes graph from junctions and network_links tables in database."""
        try:
            junction_res = await db.execute(select(Junction))
            db_junctions = junction_res.scalars().all()

            link_res = await db.execute(select(NetworkLink))
            db_links = link_res.scalars().all()

            if db_junctions and db_links:
                junction_list = [
                    {"id": str(j.name), "name": j.name, "lat": j.latitude, "lon": j.longitude}
                    for j in db_junctions
                ]
                edge_list = [
                    {
                        "from": link.from_junction,
                        "to": link.to_junction,
                        "sumo_edge_id": link.sumo_edge_id,
                        "free_flow_speed": link.free_flow_speed_kmh,
                        "capacity": link.capacity_pcu_h,
                        "length_m": link.length_m,
                    }
                    for link in db_links
                ]
                self.engine.build_graph(junction_list, edge_list)
                logger.info(
                    f"Routing graph initialized from DB with {len(junction_list)} nodes and {len(edge_list)} edges."
                )
                return
        except Exception as e:
            logger.warning(f"Failed to initialize routing graph from DB, using corridor fallback: {e}")

        # Fallback to corridor network
        self.engine.build_graph(CORRIDOR_JUNCTIONS, CORRIDOR_EDGES)

    def update_live_telemetry(self, telemetry_updates: Dict[str, Any]):
        """Updates edge weights from live telemetry updates."""
        self.engine.update_edge_weights(telemetry_updates)

    def build_traffic_data_from_junction_telemetry(
        self, telemetry_by_junction: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Translates cached JunctionTelemetry payloads into the edge-keyed

        traffic_data shape RoutingEngine.update_edge_weights() expects (SN-041).
        Each edge maps to the real approach at the real junction a vehicle
        traveling it arrives at (shared/corridor_topology.py's
        telemetry_approach) — an edge whose destination isn't a signalized
        junction has no detector data and is simply left out, never guessed.
        """
        traffic_data: Dict[str, Dict[str, Any]] = {}
        for u in self.engine.graph:
            for v, edge in self.engine.graph[u].items():
                sumo_edge_id = edge.get("sumo_edge_id")
                approach = telemetry_approach_for_edge(sumo_edge_id) if sumo_edge_id else None
                if not approach:
                    continue
                junction_id, direction = approach
                jt = telemetry_by_junction.get(junction_id)
                if not jt:
                    continue
                match = next((a for a in jt.get("approaches", []) if a.get("direction") == direction), None)
                if not match:
                    continue
                traffic_data[sumo_edge_id] = {
                    "speed": match.get("mean_speed_kmh"),
                    "density": match.get("pcu", 0.0),
                    "source": jt.get("source", "sumo"),
                    "timestamp": jt.get("_received_at", time.time()),
                }
        return traffic_data

    def find_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        profile: str = "citizen"
    ) -> Dict[str, Any]:
        """Finds optimal route for coordinates."""
        return self.engine.find_route(origin, destination, profile=profile)

    def find_route_between_nodes(
        self,
        start_node: str,
        end_node: str,
        profile: str = "emergency"
    ) -> Dict[str, Any]:
        """Finds optimal route between two node IDs."""
        return self.engine.find_route_between_nodes(start_node, end_node, profile=profile)

    def find_alternatives(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        num_routes: int = 2,
        profile: str = "citizen"
    ) -> Dict[str, Any]:
        """Finds diverse alternative routes."""
        return self.engine.find_alternatives(origin, destination, num_routes=num_routes, profile=profile)

    def get_edge_lengths_m(self, route: List[str]) -> Dict[str, float]:
        """Returns real per-link lengths (meters) for consecutive junctions on `route`.

        Sourced from the routing graph's own distance (haversine over the real
        node coordinates, or the seeded corridor length), not an assumed constant.
        """
        lengths: Dict[str, float] = {}
        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            edge = self.engine.graph.get(u, {}).get(v)
            if edge:
                lengths[f"{u}_{v}"] = edge["distance"] * 1000.0
        return lengths

    def get_edge_speeds_kmh(self, route: List[str]) -> Dict[str, float]:
        """Returns current live speed (km/h) for consecutive junctions on `route`."""
        speeds: Dict[str, float] = {}
        for i in range(len(route) - 1):
            u, v = route[i], route[i + 1]
            edge = self.engine.graph.get(u, {}).get(v)
            if edge:
                speeds[f"{u}_{v}"] = edge.get("current_speed", edge["free_flow_speed"])
        return speeds

    def get_congestion(self) -> List[Dict[str, Any]]:
        """Returns network edge congestion and staleness status."""
        edges_data = []
        for u in self.engine.graph:
            for v, data in self.engine.graph[u].items():
                edges_data.append({
                    "from": u,
                    "to": v,
                    "sumo_edge_id": data.get("sumo_edge_id", f"{u}_{v}"),
                    "distance_km": round(data["distance"], 2),
                    "current_speed_kmh": round(data["current_speed"], 1),
                    "free_flow_speed_kmh": round(data["free_flow_speed"], 1),
                    "congestion_level": self.engine.get_congestion_level(
                        data["current_speed"], data["free_flow_speed"]
                    ),
                    "stale": data.get("stale", False),
                    "source": data.get("source", "free_flow"),
                })
        return edges_data


routing_service = RoutingService.get_instance()
