import logging
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


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
        # 1. Capture the real signal plan so it can be restored afterwards.
        #    A green wave pre-empts live signals; if the plan we captured is a
        #    placeholder then restore silently returns the junction to nothing,
        #    leaving it pre-empted after the emergency has passed. Record the
        #    absence explicitly instead of inventing a plan.
        for jid in route_junction_ids:
            if jid not in self.original_plans:
                if env is not None and hasattr(env, 'get_plan'):
                    self.original_plans[jid] = env.get_plan(jid)
                else:
                    self.original_plans[jid] = None
                
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
            self._restore(route[i], env)
                
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
        for jid in event["route"]:
            self._restore(jid, env)
                
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
        
    def _restore(self, junction_id: str, env=None) -> bool:
        """Return one junction to the plan captured at activation.

        Returns False when there is nothing to restore to — either no env is
        attached or no plan was captured. The caller is left holding a junction
        that is still pre-empted, which is a condition an operator must see
        rather than one this controller should paper over.
        """
        plan = self.original_plans.get(junction_id)
        if env is None or not hasattr(env, 'restore_plan'):
            return False
        if plan is None:
            logger.warning(
                "No captured plan for junction %s; it remains pre-empted and "
                "must be released manually.", junction_id
            )
            return False
        env.restore_plan(junction_id, plan)
        return True

    def _get_approach_phase(self, from_junction: str, to_junction: str) -> int:
        """Determine which signal phase to activate for the approach based on network topology.
        Phase 0: East-West arterial green (corridor flow, e.g. J0<->J1<->J2<->J3).
        Phase 2: North-South cross street green.
        """
        fj = str(from_junction).upper()
        tj = str(to_junction).upper()

        # East-West arterial pairs along corridor
        ew_pairs = {
            ("J0", "J1"), ("J1", "J0"),
            ("J1", "J2"), ("J2", "J1"),
            ("J2", "J3"), ("J3", "J2"),
            ("J3", "J4"), ("J4", "J3"),
            ("W", "J0"), ("J3", "E"),
        }
        if (fj, tj) in ew_pairs:
            return 0

        # Check directional markers
        if any(p in fj for p in ["E_", "W_", "WEST", "EAST"]) or any(p in tj for p in ["E_", "W_", "WEST", "EAST"]):
            return 0
        if any(p in fj for p in ["N_", "S_", "NORTH", "SOUTH", "CROSS"]) or any(p in tj for p in ["N_", "S_", "NORTH", "SOUTH", "CROSS"]):
            return 2

        # Default arterial green for corridor J-nodes
        if fj.startswith("J") and tj.startswith("J"):
            return 0

        return 2
        
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
