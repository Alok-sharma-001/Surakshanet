import math
import time
import heapq
from typing import List, Dict, Tuple, Any, Optional
from shared.constants import (
    ROUTING_WEIGHTS_CITIZEN,
    ROUTING_WEIGHTS_EMERGENCY,
)


class RoutingEngine:
    """Dynamic routing engine using real-time traffic data, supporting citizen and

    emergency profiles with staleness tracking and route diversity enforcement.
    Conforms to docs/15-routing.md and docs/10-emergency-corridor.md.
    """

    STALE_THRESHOLD_S = 60.0

    def __init__(self):
        self.graph: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.node_positions: Dict[str, Tuple[float, float]] = {}
        self.node_names: Dict[str, str] = {}
        self.edge_by_sumo_id: Dict[str, Tuple[str, str]] = {}

    def build_graph(self, junctions: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """Build weighted directed graph from junctions and edges."""
        self.graph = {}
        self.node_positions = {}
        self.node_names = {}
        self.edge_by_sumo_id = {}

        for j in junctions:
            jid = str(j["id"])
            self.graph[jid] = {}
            self.node_positions[jid] = (float(j["lat"]), float(j["lon"]))
            self.node_names[jid] = j.get("name", jid)

        now = time.time()
        for e in edges:
            u, v = str(e["from"]), str(e["to"])
            if u not in self.graph:
                self.graph[u] = {}

            # Distance in km via haversine
            pos_u = self.node_positions.get(u, (0.0, 0.0))
            pos_v = self.node_positions.get(v, (0.0, 0.0))
            dist = self._haversine(pos_u[0], pos_u[1], pos_v[0], pos_v[1])
            if dist <= 0.0:
                dist = e.get("length_m", 300.0) / 1000.0

            ffs = float(e.get("free_flow_speed", 50.0))
            cap = float(e.get("capacity", 2000.0))
            sumo_id = e.get("sumo_edge_id", f"{u}_{v}")

            self.edge_by_sumo_id[sumo_id] = (u, v)
            base_travel_time = (dist / max(ffs, 1.0)) * 60.0  # in minutes

            self.graph[u][v] = {
                "distance": dist,
                "weight": dist,
                "free_flow_speed": ffs,
                "speed": ffs,
                "current_speed": ffs,
                "travel_time": base_travel_time,
                "capacity": cap,
                "density": 0.0,
                "last_updated": now,
                "stale": False,
                "source": "free_flow",
                "sumo_edge_id": sumo_id,
            }

    def update_edge_weights(self, traffic_data: Dict[str, Any], current_time: Optional[float] = None):
        """Update edge weights based on real-time congestion and telemetry.

        traffic_data maps edge identifier ('u-v', 'u_v', or sumo_edge_id) to:
        {'speed': float, 'density': float, 'source': str, 'timestamp': float}
        """
        now = current_time if current_time is not None else time.time()

        for u in self.graph:
            for v in self.graph[u]:
                edge_data = self.graph[u][v]
                edge_id_hyphen = f"{u}-{v}"
                edge_id_underscore = f"{u}_{v}"
                sumo_id = edge_data.get("sumo_edge_id", "")

                matched_data = None
                if edge_id_hyphen in traffic_data:
                    matched_data = traffic_data[edge_id_hyphen]
                elif edge_id_underscore in traffic_data:
                    matched_data = traffic_data[edge_id_underscore]
                elif sumo_id in traffic_data:
                    matched_data = traffic_data[sumo_id]

                if matched_data:
                    ts = matched_data.get("timestamp", now)
                    is_stale = (now - ts) > self.STALE_THRESHOLD_S

                    if is_stale:
                        # Revert to free-flow speed on stale data (SN-041 / docs/15-routing.md §2)
                        speed = edge_data["free_flow_speed"]
                        density = 0.0
                        edge_data["stale"] = True
                    else:
                        raw_speed = matched_data.get("speed")
                        # None means nothing was resolvable this window (e.g. an
                        # uncalibrated vision camera) — fall back to the edge's
                        # static free-flow speed rather than crash on float(None).
                        speed = max(1.0, float(raw_speed)) if raw_speed is not None else edge_data["free_flow_speed"]
                        density = float(matched_data.get("density", 0.0))
                        edge_data["stale"] = False

                    travel_time = (edge_data["distance"] / speed) * 60.0
                    edge_data["current_speed"] = speed
                    edge_data["travel_time"] = travel_time
                    edge_data["density"] = density
                    edge_data["last_updated"] = ts
                    edge_data["source"] = matched_data.get("source", "sumo")

                    # Compute base citizen weight
                    cap = max(edge_data["capacity"], 100.0)
                    congestion_factor = min(1.0, density / cap)
                    edge_data["weight"] = (
                        ROUTING_WEIGHTS_CITIZEN["travel_time"] * travel_time
                        + ROUTING_WEIGHTS_CITIZEN["congestion"] * congestion_factor * 10.0
                        + ROUTING_WEIGHTS_CITIZEN["distance"] * edge_data["distance"]
                    )
                else:
                    # Check if previous telemetry has become stale
                    if (now - edge_data["last_updated"]) > self.STALE_THRESHOLD_S:
                        edge_data["stale"] = True
                        edge_data["current_speed"] = edge_data["free_flow_speed"]
                        edge_data["travel_time"] = (edge_data["distance"] / edge_data["free_flow_speed"]) * 60.0
                        edge_data["weight"] = (
                            ROUTING_WEIGHTS_CITIZEN["travel_time"] * edge_data["travel_time"]
                            + ROUTING_WEIGHTS_CITIZEN["distance"] * edge_data["distance"]
                        )

    def _get_edge_weight(self, u: str, v: str, profile: str = "citizen") -> float:
        """Computes edge cost according to specified profile (docs/15-routing.md §3)."""
        data = self.graph[u][v]
        distance = data["distance"]

        if profile == "emergency":
            # Emergency profile: 0.7 * travel_time + 0.3 * distance — congestion deliberately excluded
            # because the green corridor clears standing traffic ahead of the vehicle.
            emergency_speed = data["free_flow_speed"] * 1.3
            emergency_travel_time = (distance / max(emergency_speed, 1.0)) * 60.0
            return (
                ROUTING_WEIGHTS_EMERGENCY["travel_time"] * emergency_travel_time
                + ROUTING_WEIGHTS_EMERGENCY["distance"] * distance
            )
        else:
            # Citizen profile: 0.4 * travel_time + 0.3 * congestion + 0.3 * distance
            travel_time = data["travel_time"]
            density = data.get("density", 0.0)
            cap = max(data.get("capacity", 2000.0), 100.0)
            congestion_factor = min(1.0, density / cap)
            return (
                ROUTING_WEIGHTS_CITIZEN["travel_time"] * travel_time
                + ROUTING_WEIGHTS_CITIZEN["congestion"] * congestion_factor * 10.0
                + ROUTING_WEIGHTS_CITIZEN["distance"] * distance
            )

    def find_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        profile: str = "citizen",
        penalties: Optional[Dict[Tuple[str, str], float]] = None
    ) -> Dict[str, Any]:
        """Find best route using A* search under given weight profile."""
        if not self.graph:
            return {"error": "Graph not initialized", "path": []}

        start_node = self._find_nearest_node(origin[0], origin[1])
        end_node = self._find_nearest_node(destination[0], destination[1])

        if not start_node or not end_node:
            return {"error": "No nearby nodes found", "path": []}

        return self._astar_search(start_node, end_node, profile=profile, penalties=penalties)

    def find_route_between_nodes(
        self,
        start_node: str,
        end_node: str,
        profile: str = "emergency"
    ) -> Dict[str, Any]:
        """Find route directly between two known junction node IDs."""
        if start_node not in self.graph or end_node not in self.graph:
            return {"error": f"Invalid nodes {start_node} or {end_node}", "path": []}
        return self._astar_search(start_node, end_node, profile=profile)

    def find_alternatives(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        num_routes: int = 3,
        profile: str = "citizen"
    ) -> Dict[str, Any]:
        """Find up to K alternative routes ensuring diverse paths (< 70% edge overlap).

        Returns dict with 'primary', 'alternatives', and 'advice'.
        """
        primary = self.find_route(origin, destination, profile=profile)
        if "error" in primary or not primary.get("path"):
            return {
                "primary": primary,
                "alternatives": [],
                "advice": "no route found"
            }

        primary_path = primary["path"]
        primary_edges = set(zip(primary_path[:-1], primary_path[1:]))

        alternatives: List[Dict[str, Any]] = []
        penalties: Dict[Tuple[str, str], float] = {}

        # Successively penalize edges in found paths to find diverse alternatives
        for _ in range(num_routes):
            # Accumulate 1.8x penalty on edges in previous routes
            for u, v in primary_edges:
                penalties[(u, v)] = penalties.get((u, v), 1.0) * 1.8
            for alt in alternatives:
                for u, v in zip(alt["path"][:-1], alt["path"][1:]):
                    penalties[(u, v)] = penalties.get((u, v), 1.0) * 1.8

            alt_route = self.find_route(origin, destination, profile=profile, penalties=penalties)
            if "error" in alt_route or not alt_route.get("path"):
                break

            alt_path = alt_route["path"]
            alt_edges = set(zip(alt_path[:-1], alt_path[1:]))

            # Check edge overlap with primary and all accepted alternatives (< 70% edge overlap)
            overlap_primary = len(alt_edges & primary_edges) / max(len(primary_edges), 1)
            too_similar = overlap_primary > 0.70

            for prev_alt in alternatives:
                prev_edges = set(zip(prev_alt["path"][:-1], prev_alt["path"][1:]))
                if len(alt_edges & prev_edges) / max(len(prev_edges), 1) > 0.70:
                    too_similar = True
                    break

            if not too_similar and alt_path != primary_path:
                added_time_s = max(0.0, (alt_route["eta_minutes"] - primary["eta_minutes"]) * 60.0)
                alt_route["added_time_s"] = round(added_time_s, 1)
                alt_route["added_distance_km"] = round(max(0.0, alt_route["distance_km"] - primary["distance_km"]), 2)
                alt_route["reason"] = f"Alternative bypassing {len(primary_edges & alt_edges)} shared corridor links"
                alternatives.append(alt_route)

        # Honest empty case when no alternative improves or is sufficiently distinct
        if not alternatives:
            advice = "no better alternative — consider delayed departure"
        else:
            advice = f"Found {len(alternatives)} diverse alternative routes"

        return {
            "primary": primary,
            "alternatives": alternatives,
            "advice": advice
        }

    def _astar_search(
        self,
        start: str,
        end: str,
        profile: str = "citizen",
        penalties: Optional[Dict[Tuple[str, str], float]] = None
    ) -> Dict[str, Any]:
        """A* search algorithm implementation with custom profiles and penalties."""
        open_set = []
        heapq.heappush(open_set, (0.0, start))

        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {node: float("inf") for node in self.graph}
        g_score[start] = 0.0

        f_score: Dict[str, float] = {node: float("inf") for node in self.graph}
        f_score[start] = self._heuristic(start, end)

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == end:
                path = self._reconstruct_path(came_from, current)
                return self._calculate_route_metrics(path, profile=profile)

            for neighbor in self.graph.get(current, {}):
                base_weight = self._get_edge_weight(current, neighbor, profile=profile)
                penalty = (penalties.get((current, neighbor), 1.0)) if penalties else 1.0
                effective_weight = base_weight * penalty

                tentative_g = g_score[current] + effective_weight

                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, end)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return {"error": "No path found", "path": []}

    def _reconstruct_path(self, came_from: Dict[str, str], current: str) -> List[str]:
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        return total_path[::-1]

    def _calculate_route_metrics(self, path: List[str], profile: str = "citizen") -> Dict[str, Any]:
        distance = 0.0
        eta_minutes = 0.0
        min_speed = float("inf")
        has_stale_data = False

        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            data = self.graph[u][v]
            distance += data["distance"]
            eta_minutes += data["travel_time"]
            min_speed = min(min_speed, data["current_speed"])
            if data.get("stale", False):
                has_stale_data = True

        congestion = self.get_congestion_level(min_speed, 50.0)

        # Build readable route text with junction names
        route_names = [self.node_names.get(n, n) for n in path]
        route_text = " → ".join(route_names)

        return {
            "path": path,
            "route_text": route_text,
            "distance_km": round(distance, 2),
            "eta_minutes": round(eta_minutes, 2),
            "travel_time_s": round(eta_minutes * 60.0, 1),
            "congestion_level": congestion,
            "stale": has_stale_data,
            "profile": profile,
        }

    def _find_nearest_node(self, lat: float, lon: float) -> Optional[str]:
        """Find the nearest graph node to given coordinates."""
        nearest = None
        min_dist = float("inf")
        for node, pos in self.node_positions.items():
            dist = self._haversine(lat, lon, pos[0], pos[1])
            if dist < min_dist:
                min_dist = dist
                nearest = node
        return nearest

    def _heuristic(self, node_a: str, node_b: str) -> float:
        """A* heuristic: geographical distance in km."""
        pos_a = self.node_positions.get(node_a)
        pos_b = self.node_positions.get(node_b)
        if pos_a and pos_b:
            return self._haversine(pos_a[0], pos_a[1], pos_b[0], pos_b[1])
        return 0.0

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate the great circle distance between two points in km."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2.0) ** 2
            + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
        )
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c

    def get_congestion_level(self, speed: float, free_flow_speed: float) -> str:
        """Determine congestion level based on speed ratio."""
        ratio = speed / free_flow_speed if free_flow_speed > 0 else 0
        if ratio > 0.8:
            return "FREE_FLOW"
        elif ratio > 0.5:
            return "MODERATE"
        elif ratio > 0.2:
            return "HEAVY"
        else:
            return "GRIDLOCK"
