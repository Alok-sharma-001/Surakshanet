import math
import heapq
from typing import List, Dict, Tuple, Any

class RoutingEngine:
    """Dynamic routing engine using real-time traffic data."""
    
    def __init__(self):
        self.graph = {}
        self.node_positions = {}
        
    def build_graph(self, junctions: List[Dict[str, Any]], edges: List[Dict[str, Any]]):
        """Build weighted directed graph from junctions and edges."""
        self.graph = {}
        self.node_positions = {}
        
        for j in junctions:
            jid = j["id"]
            self.graph[jid] = {}
            self.node_positions[jid] = (j["lat"], j["lon"])
            
        for e in edges:
            u, v = e["from"], e["to"]
            if u not in self.graph:
                self.graph[u] = {}
            # Base weight is distance in km
            dist = self._haversine(self.node_positions[u][0], self.node_positions[u][1],
                                   self.node_positions[v][0], self.node_positions[v][1])
            self.graph[u][v] = {
                "distance": dist,
                "weight": dist,  # Initial weight based on distance
                "speed": e.get("free_flow_speed", 50.0),
                "capacity": e.get("capacity", 1000)
            }
            
    def update_edge_weights(self, traffic_data: Dict[str, Any]):
        """Update edge weights based on real-time congestion."""
        for u in self.graph:
            for v in self.graph[u]:
                edge_id = f"{u}-{v}"
                edge_data = self.graph[u][v]
                
                if edge_id in traffic_data:
                    data = traffic_data[edge_id]
                    speed = max(1.0, data.get("speed", edge_data["speed"]))
                    travel_time = edge_data["distance"] / speed * 60  # in minutes
                    
                    # Calculate congestion factor based on density
                    density = data.get("density", 0.0)
                    capacity = edge_data["capacity"]
                    congestion_factor = min(1.0, density / capacity)
                    
                    # Update weight: weighted sum of travel time, congestion, and distance
                    weight = 0.4 * travel_time + 0.3 * congestion_factor * 10 + 0.3 * edge_data["distance"]
                    self.graph[u][v]["weight"] = weight
                    self.graph[u][v]["current_speed"] = speed
                    self.graph[u][v]["travel_time"] = travel_time
                    
    def find_route(self, origin: Tuple[float, float], destination: Tuple[float, float]) -> Dict[str, Any]:
        """Find best route using A* search."""
        if not self.graph:
            return {"error": "Graph not initialized"}
            
        # Find nearest nodes to origin and destination
        start_node = self._find_nearest_node(origin[0], origin[1])
        end_node = self._find_nearest_node(destination[0], destination[1])
        
        return self._astar_search(start_node, end_node)
        
    def find_alternatives(self, origin: Tuple[float, float], destination: Tuple[float, float], num_routes: int = 3) -> List[Dict[str, Any]]:
        """Find K alternative routes using a penalty-based approach."""
        if not self.graph:
            return []
            
        start_node = self._find_nearest_node(origin[0], origin[1])
        end_node = self._find_nearest_node(destination[0], destination[1])
        
        routes = []
        original_weights = {u: {v: self.graph[u][v]["weight"] for v in self.graph[u]} for u in self.graph}
        
        for _ in range(num_routes):
            route = self._astar_search(start_node, end_node)
            if "error" in route or not route["path"]:
                break
                
            routes.append(route)
            
            # Penalize edges in the found route to force finding alternatives
            path = route["path"]
            for i in range(len(path) - 1):
                u, v = path[i], path[i+1]
                self.graph[u][v]["weight"] *= 1.5  # Increase penalty factor
                
        # Restore original weights
        for u in original_weights:
            for v in original_weights[u]:
                self.graph[u][v]["weight"] = original_weights[u][v]
                
        return routes

    def _astar_search(self, start: str, end: str) -> Dict[str, Any]:
        """A* search algorithm implementation."""
        open_set = []
        heapq.heappush(open_set, (0, start))
        
        came_from = {}
        g_score = {node: float('inf') for node in self.graph}
        g_score[start] = 0
        
        f_score = {node: float('inf') for node in self.graph}
        f_score[start] = self._heuristic(start, end)
        
        while open_set:
            _, current = heapq.heappop(open_set)
            
            if current == end:
                path = self._reconstruct_path(came_from, current)
                return self._calculate_route_metrics(path)
                
            for neighbor, data in self.graph[current].items():
                tentative_g_score = g_score[current] + data["weight"]
                
                if tentative_g_score < g_score.get(neighbor, float('inf')):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + self._heuristic(neighbor, end)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))
                    
        return {"error": "No path found", "path": []}
        
    def _reconstruct_path(self, came_from: Dict[str, str], current: str) -> List[str]:
        total_path = [current]
        while current in came_from:
            current = came_from[current]
            total_path.append(current)
        return total_path[::-1]
        
    def _calculate_route_metrics(self, path: List[str]) -> Dict[str, Any]:
        distance = 0.0
        eta = 0.0
        min_speed = float('inf')
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            data = self.graph[u][v]
            distance += data["distance"]
            eta += data.get("travel_time", data["distance"] / data["speed"] * 60)
            min_speed = min(min_speed, data.get("current_speed", data["speed"]))
            
        congestion = self.get_congestion_level(min_speed, 50.0) # Assuming 50 default FFS
        
        return {
            "path": path,
            "distance_km": round(distance, 2),
            "eta_minutes": round(eta, 2),
            "congestion_level": congestion
        }

    def _find_nearest_node(self, lat: float, lon: float) -> str:
        """Find the nearest graph node to given coordinates."""
        nearest = None
        min_dist = float('inf')
        for node, pos in self.node_positions.items():
            dist = self._haversine(lat, lon, pos[0], pos[1])
            if dist < min_dist:
                min_dist = dist
                nearest = node
        return nearest

    def _heuristic(self, node_a: str, node_b: str) -> float:
        """A* heuristic: geographical distance."""
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
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
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
