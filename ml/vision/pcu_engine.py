import logging
from typing import Dict

logger = logging.getLogger(__name__)

try:
    from shared.constants import PCU_FACTORS
except ImportError:
    PCU_FACTORS = {
        'car': 1.0,
        'motorcycle': 0.5,
        'bus': 3.0,
        'truck': 3.0,
        'auto_rickshaw': 1.0,
        'bicycle': 0.2
    }

class PCUEngine:
    """Dedicated PCU calculation engine."""
    
    def calculate_approach_demand(self, vehicle_counts: Dict[str, int]) -> float:
        """Total PCU for one approach."""
        pcu = 0.0
        for vclass, count in vehicle_counts.items():
            pcu += count * PCU_FACTORS.get(vclass, 1.0)
        return pcu
        
    def calculate_junction_demand(self, approaches: Dict[str, Dict[str, int]]) -> Dict[str, float]:
        """PCU for all 4 approaches."""
        result = {}
        for approach_name, counts in approaches.items():
            result[approach_name] = self.calculate_approach_demand(counts)
        return result
        
    def get_dominant_approach(self, junction_demand: Dict[str, float]) -> str:
        """Which approach has highest demand."""
        if not junction_demand:
            return ""
        return max(junction_demand.items(), key=lambda x: x[1])[0]
        
    def calculate_saturation_ratio(self, demand_pcu: float, capacity_pcu: float) -> float:
        """Demand/capacity ratio."""
        if capacity_pcu <= 0:
            return 0.0
        return demand_pcu / capacity_pcu
        
    def classify_congestion_level(self, saturation_ratio: float) -> str:
        """FREE_FLOW/STABLE/APPROACHING_CAPACITY/CONGESTED/GRIDLOCK based on V/C ratio."""
        if saturation_ratio < 0.5:
            return "FREE_FLOW"
        elif saturation_ratio < 0.75:
            return "STABLE"
        elif saturation_ratio < 0.9:
            return "APPROACHING_CAPACITY"
        elif saturation_ratio <= 1.0:
            return "CONGESTED"
        else:
            return "GRIDLOCK"
