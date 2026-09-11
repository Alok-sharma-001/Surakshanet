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
        self.incident_penalties: Dict[Tuple[str, str], float] = {}
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

    def apply_incident_penalty(self, link_id: str, penalty: float = 100.0) -> Optional[Tuple[str, str]]:
        """SN-093: Penalises affected link in routing graph on incident confirmation."""
        from shared.corridor_topology import edge_for_telemetry_approach
        found_edge = None
        for u in self.engine.graph:
            for v, edge_data in self.engine.graph[u].items():
                sumo_id = edge_data.get("sumo_edge_id", "")
                if sumo_id == link_id or f"{u}_{v}" == link_id or f"E_{u}_{v}" == link_id or f"{u}_to_{v}" == link_id:
                    self.incident_penalties[(u, v)] = penalty
                    found_edge = (u, v)

        if not found_edge and "_" in link_id:
            # Check if link_id is (junction, direction) like "J2_W"
            parts = link_id.split("_", 1)
            mapped_edge = edge_for_telemetry_approach(parts[0], parts[1])
            if mapped_edge:
                for u in self.engine.graph:
                    for v, edge_data in self.engine.graph[u].items():
                        if edge_data.get("sumo_edge_id") == mapped_edge:
                            self.incident_penalties[(u, v)] = penalty
                            found_edge = (u, v)

        if not found_edge:
            clean = link_id.replace("E_", "").replace("to_", "")
            parts = [p for p in clean.split("_") if p]
            if len(parts) >= 2 and parts[0] in self.engine.graph and parts[1] in self.engine.graph[parts[0]]:
                self.incident_penalties[(parts[0], parts[1])] = penalty
                found_edge = (parts[0], parts[1])
        logger.info(f"Applied routing penalty {penalty} to link {link_id} (edge {found_edge})")
        return found_edge

    def clear_incident_penalty(self, link_id: str):
        """Clears incident penalty on dismissal or resolution."""
        from shared.corridor_topology import edge_for_telemetry_approach
        to_remove = []
        mapped_edge = None
        if "_" in link_id:
            parts = link_id.split("_", 1)
            mapped_edge = edge_for_telemetry_approach(parts[0], parts[1])

        for (u, v) in self.incident_penalties:
            edge_data = self.engine.graph.get(u, {}).get(v, {})
            sumo_id = edge_data.get("sumo_edge_id", "")
            if (
                sumo_id == link_id
                or f"{u}_{v}" == link_id
                or f"E_{u}_{v}" == link_id
                or f"{u}_to_{v}" == link_id
                or (mapped_edge and sumo_id == mapped_edge)
            ):
                to_remove.append((u, v))
        for k in to_remove:
            self.incident_penalties.pop(k, None)
        logger.info(f"Cleared routing penalties for link {link_id}")

    def recompute_incident_alternatives(self, link_id: str) -> Dict[str, Any]:
        """SN-093: Recomputes alternative routes avoiding the penalized incident link."""
        from shared.corridor_topology import edge_for_telemetry_approach
        edge = None
        mapped_edge = None
        if "_" in link_id:
            parts = link_id.split("_", 1)
            mapped_edge = edge_for_telemetry_approach(parts[0], parts[1])

        for (u, v) in self.incident_penalties:
            edge_data = self.engine.graph.get(u, {}).get(v, {})
            sumo_id = edge_data.get("sumo_edge_id", "")
            if (
                sumo_id == link_id
                or f"{u}_{v}" == link_id
                or f"E_{u}_{v}" == link_id
                or f"{u}_to_{v}" == link_id
                or (mapped_edge and sumo_id == mapped_edge)
            ):
                edge = (u, v)
                break

        if not edge and self.incident_penalties:
            edge = next(iter(self.incident_penalties))

        if not edge:
            nodes = list(self.engine.node_positions.keys())
            if len(nodes) >= 2:
                u, v = nodes[0], nodes[-1]
            else:
                return {"path": [], "alternatives": []}
        else:
            u, v = edge

        orig_coords = self.engine.node_positions.get(u)
        dest_coords = self.engine.node_positions.get(v)
        if orig_coords and dest_coords:
            return self.engine.find_alternatives(
                orig_coords,
                dest_coords,
                num_routes=2,
                profile="citizen",
                penalties=dict(self.incident_penalties),
            )
        return {"path": [], "alternatives": []}

    def find_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        profile: str = "citizen",
        penalties: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> Dict[str, Any]:
        """Finds optimal route for coordinates, respecting active incident penalties."""
        active_penalties = dict(self.incident_penalties)
        if penalties:
            active_penalties.update(penalties)
        return self.engine.find_route(origin, destination, profile=profile, penalties=active_penalties)

    def find_route_between_nodes(
        self,
        start_node: str,
        end_node: str,
        profile: str = "emergency",
        penalties: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> Dict[str, Any]:
        """Finds optimal route between two node IDs."""
        active_penalties = dict(self.incident_penalties)
        if penalties:
            active_penalties.update(penalties)
        return self.engine.find_route_between_nodes(
            start_node, end_node, profile=profile, penalties=active_penalties
        )

    def find_alternatives(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        num_routes: int = 2,
        profile: str = "citizen",
        penalties: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> Dict[str, Any]:
        """Finds diverse alternative routes."""
        active_penalties = dict(self.incident_penalties)
        if penalties:
            active_penalties.update(penalties)
        return self.engine.find_alternatives(
            origin, destination, num_routes=num_routes, profile=profile, penalties=active_penalties
        )

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
