import datetime
from typing import Dict, Any

class WebsterFallback:
    """Webster Time-of-Day fallback controller for traffic signals."""
    
    def __init__(self):
        self.plans = {
            'morning_peak': {
                'ns_green': 50,
                'ew_green': 40,
                'cycle': 94
            },
            'afternoon_offpeak': {
                'ns_green': 35,
                'ew_green': 35,
                'cycle': 74
            },
            'evening_peak': {
                'ns_green': 60,
                'ew_green': 45,
                'cycle': 109
            },
            'night': {
                'ns_green': 30,
                'ew_green': 30,
                'cycle': 64
            }
        }
        
    def get_plan(self, time_of_day: str) -> Dict[str, int]:
        """Get signal timing plan for a specific time of day."""
        return self.plans.get(time_of_day, self.plans['afternoon_offpeak'])
        
    def get_current_plan(self) -> Dict[str, int]:
        """Determine plan based on current time of day."""
        current_hour = datetime.datetime.now().hour
        
        if 7 <= current_hour < 10:
            return self.get_plan('morning_peak')
        elif 10 <= current_hour < 16:
            return self.get_plan('afternoon_offpeak')
        elif 16 <= current_hour < 20:
            return self.get_plan('evening_peak')
        else:
            return self.get_plan('night')
            
    def calculate_webster_optimal(self, demands: Dict[str, float]) -> Dict[str, int]:
        """Calculate optimal cycle length and green splits using Webster's formula.
        
        Args:
            demands: Dict with critical flow ratios (Y) for each phase. e.g., {'ns': 0.4, 'ew': 0.3}
            
        Returns:
            Dict with optimal green times and cycle length.
        """
        L = 2 * 2  # Total lost time (assume 2 phases, 2s all-red per phase)
        Y = sum(demands.values())
        
        if Y >= 1.0:
            Y = 0.95  # Prevent division by zero or negative cycle length
            
        C0 = (1.5 * L + 5) / (1 - Y)
        
        # Enforce practical bounds on cycle length
        C0 = max(40, min(150, int(round(C0))))
        
        effective_green = C0 - L
        
        splits = {}
        for phase, y in demands.items():
            green_time = int(round((y / Y) * effective_green))
            splits[f"{phase}_green"] = green_time
            
        splits['cycle'] = C0
        return splits
        
    def apply_to_sumo(self, env, tl_id: str, plan: Dict[str, int]):
        """Set SUMO traffic light to the Webster plan.
        
        Args:
            env: SUMO environment wrapper
            tl_id: Traffic light ID
            plan: Dictionary with green times
        """
        # This requires specific traci commands to build and upload a complete logic
        if not hasattr(env, 'traci'):
            return
            
        ns_g = plan.get('ns_green', 40)
        ew_g = plan.get('ew_green', 40)
        
        # Assuming simple 4-phase cycle: NS_G, NS_Y, EW_G, EW_Y
        phases = [
            env.traci.trafficlight.Phase(ns_g, "GGgrrrGGgrrr"), # NS green
            env.traci.trafficlight.Phase(3, "yyyrrryyyrrr"),    # NS yellow
            env.traci.trafficlight.Phase(ew_g, "rrrGGgrrrGGg"), # EW green
            env.traci.trafficlight.Phase(3, "rrryyyrrryyy")     # EW yellow
        ]
        
        logic = env.traci.trafficlight.Logic("webster_fallback", 0, 0, phases)
        env.traci.trafficlight.setProgramLogic(tl_id, logic)
