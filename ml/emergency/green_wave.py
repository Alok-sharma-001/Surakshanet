import time
from typing import Dict, List, Any, Optional

class GreenWaveController:
    """Emergency green-wave controller for traffic pre-emption."""
    
    def __init__(self, lookahead: int = 3, green_hold_s: float = 30):
        self.lookahead = lookahead
        self.green_hold_s = green_hold_s
        
        # State tracking
        self.active_events = {}
        self.original_plans = {}
        
    def activate(self, event_id: str, priority: str, vehicle_type: str, route_junction_ids: List[str], env=None) -> Dict[str, Any]:
        """Activate a green wave for an emergency vehicle route."""
        # 1. Store original plans
        for jid in route_junction_ids:
            if jid not in self.original_plans:
                # In real app, fetch current plan from env/DB
                self.original_plans[jid] = {"mock_plan": True}
                
        # 2. Pre-empt upcoming junctions
        active_junctions = route_junction_ids[:self.lookahead]
        
        # Example of setting states in env (pseudo-code depending on SUMO env structure)
        if env is not None and hasattr(env, 'set_green_wave'):
            for i in range(len(active_junctions) - 1):
                from_j = route_junction_ids[i] if i > 0 else "start"
                to_j = active_junctions[i]
                phase = self._get_approach_phase(from_j, to_j)
                env.set_green_wave(to_j, phase, self.green_hold_s)
                
        # 3. Store event
        event_data = {
            "id": event_id,
            "priority": priority,
            "vehicle_type": vehicle_type,
            "route": route_junction_ids,
            "current_index": 0,
            "active_junctions": active_junctions,
            "timestamp": time.time()
        }
        self.active_events[event_id] = event_data
        
        return {"status": "activated", "event": event_data}
        
    def update_position(self, event_id: str, current_junction_id: str, env=None) -> Dict[str, Any]:
        """Update vehicle position and adjust green wave."""
        if event_id not in self.active_events:
            return {"status": "error", "message": "Event not found"}
            
        event = self.active_events[event_id]
        route = event["route"]
        
        try:
            curr_idx = route.index(current_junction_id)
        except ValueError:
            return {"status": "error", "message": "Junction not in route"}
            
        # Vehicle passed previous junctions; restore them
        for i in range(event["current_index"], curr_idx):
            passed_jid = route[i]
            if env is not None and hasattr(env, 'restore_plan'):
                env.restore_plan(passed_jid, self.original_plans.get(passed_jid))
                
        # Update index
        event["current_index"] = curr_idx
        
        # Pre-empt next batch of junctions
        end_idx = min(len(route), curr_idx + self.lookahead)
        new_active = route[curr_idx:end_idx]
        event["active_junctions"] = new_active
        
        if env is not None and hasattr(env, 'set_green_wave'):
            for jid in new_active:
                phase = self._get_approach_phase("dummy_from", jid)
                env.set_green_wave(jid, phase, self.green_hold_s)
                
        return {"status": "updated", "event": event}
        
    def deactivate(self, event_id: str, env=None) -> Dict[str, Any]:
        """Deactivate a green wave and restore normal operations."""
        if event_id not in self.active_events:
            return {"status": "error", "message": "Event not found"}
            
        event = self.active_events[event_id]
        
        # Restore all affected junctions
        if env is not None and hasattr(env, 'restore_plan'):
            for jid in event["route"]:
                env.restore_plan(jid, self.original_plans.get(jid))
                
        # Clean up plans if no other events use them
        for jid in event["route"]:
            # Check if any other active event uses this junction
            in_use = any(jid in e["route"] for eid, e in self.active_events.items() if eid != event_id)
            if not in_use and jid in self.original_plans:
                del self.original_plans[jid]
                
        del self.active_events[event_id]
        
        return {"status": "deactivated"}
        
    def get_status(self, event_id: Optional[str] = None) -> Dict[str, Any]:
        """Get status of one or all events."""
        if event_id:
            return self.active_events.get(event_id, {})
        return {"active_events": list(self.active_events.values())}
        
    def get_active_events(self) -> List[Dict[str, Any]]:
        """List all active emergency events."""
        return list(self.active_events.values())
        
    def _get_approach_phase(self, from_junction: str, to_junction: str) -> int:
        """Determine which signal phase to activate for the approach.
        In a full implementation, this maps network topology to phase indices.
        """
        # Placeholder mapping
        return 0
        
    def _resolve_priority(self, event1: Dict[str, Any], event2: Dict[str, Any]) -> str:
        """Determine which event wins in case of conflict at a junction."""
        priority_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        p1 = priority_map.get(event1.get("priority", "LOW"), 0)
        p2 = priority_map.get(event2.get("priority", "LOW"), 0)
        
        if p1 > p2:
            return event1["id"]
        elif p2 > p1:
            return event2["id"]
        else:
            # Older event wins tie-breaker
            return event1["id"] if event1["timestamp"] < event2["timestamp"] else event2["id"]
