import os
import sys
import json
import logging
from typing import Optional, Dict, Any, List

try:
    import libsumo as traci
except ImportError:
    import traci

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

class SumoEnvironment:
    """Eclipse SUMO environment wrapper for traffic signal control.
    
    Provides a clean interface to:
    - Start/stop SUMO simulation
    - Get junction state (queue lengths, speeds, phases)
    - Set traffic light phases via TraCI
    - Collect performance metrics
    """
    
    def __init__(self, net_file: str, route_file: str, config_file: Optional[str] = None,
                 gui: bool = False, step_length: float = 1.0, begin: int = 0, end: int = 3600,
                 additional_files: Optional[list] = None):
        self.net_file = net_file
        self.route_file = route_file
        self.config_file = config_file
        self.gui = gui
        self.step_length = step_length
        self.begin = begin
        self.end = end
        self.additional_files = additional_files or []
        
        self.junction_ids: List[str] = []
        self.tl_ids: List[str] = []
        
        self.total_waiting_time = 0.0
        self.total_departed = 0
        self.total_arrived = 0
        self.step_count = 0
        self._is_running = False
        
        if 'SUMO_HOME' not in os.environ:
            logger.warning("SUMO_HOME not set in environment. TraCI might fail.")
            
    def start(self):
        """Start SUMO simulation with TraCI connection."""
        if self._is_running:
            logger.warning("Simulation is already running.")
            return

        sumo_binary = "sumo-gui" if self.gui else "sumo"
        cmd = [sumo_binary]
        
        if self.config_file and os.path.exists(self.config_file):
            cmd.extend(["-c", self.config_file])
        else:
            cmd.extend(["-n", self.net_file, "-r", self.route_file])
            if self.additional_files:
                cmd.extend(["-a", ",".join(self.additional_files)])
                
        cmd.extend([
            "--step-length", str(self.step_length),
            "-b", str(self.begin),
            "-e", str(self.end),
            "--waiting-time-memory", "10000"
        ])
        
        try:
            traci.start(cmd)
            self._is_running = True
            
            self.tl_ids = list(traci.trafficlight.getIDList())
            self.junction_ids = list(traci.junction.getIDList())
            
            self.total_waiting_time = 0.0
            self.total_departed = 0
            self.total_arrived = 0
            self.step_count = 0
            
            logger.info(f"Started SUMO with {len(self.tl_ids)} traffic lights and {len(self.junction_ids)} junctions.")
        except Exception as e:
            logger.error(f"Failed to start SUMO: {e}")
            raise
            
    def step(self, n_steps: int = 1) -> dict:
        """Advance simulation by n steps and return current state."""
        if not self._is_running:
            raise RuntimeError("Simulation is not running.")
            
        for _ in range(n_steps):
            traci.simulationStep()
            self.step_count += 1
            
            # Simple metric collection
            self.total_departed += traci.simulation.getDepartedNumber()
            self.total_arrived += traci.simulation.getArrivedNumber()
            
            # Collect waiting time
            for veh_id in traci.vehicle.getIDList():
                self.total_waiting_time += traci.vehicle.getWaitingTime(veh_id)
                
        return self.get_state()
        
    def get_state(self) -> dict:
        """Get current state of all junctions."""
        if not self._is_running:
            return {}
            
        state = {
            "simulation_time": traci.simulation.getTime(),
            "step_count": self.step_count,
            "junctions": {},
            "global_metrics": {
                "total_vehicles": self.total_departed - self.total_arrived,
                "total_waiting_time": self.total_waiting_time,
                "throughput": self.total_arrived
            }
        }
        
        for tl_id in self.tl_ids:
            try:
                controlled_links = traci.trafficlight.getControlledLinks(tl_id)
                edges = set()
                for link in controlled_links:
                    if link:
                        edges.add(link[0][0].split('_')[0]) # Get base edge ID
                        
                approaches = {}
                for edge in edges:
                    direction = self._get_approach_direction(edge)
                    veh_count = traci.edge.getLastStepVehicleNumber(edge)
                    queue_len = traci.edge.getLastStepHaltingNumber(edge)
                    avg_speed = traci.edge.getLastStepMeanSpeed(edge)
                    
                    # Calculate PCU
                    pcu = 0.0
                    for veh_id in traci.edge.getLastStepVehicleIDs(edge):
                        vclass = traci.vehicle.getVehicleClass(veh_id)
                        pcu += PCU_FACTORS.get(vclass, 1.0)
                        
                    approaches[direction] = {
                        "pcu": pcu,
                        "queue_length": queue_len,
                        "avg_speed": avg_speed,
                        "vehicle_count": veh_count
                    }
                    
                state["junctions"][tl_id] = {
                    "approaches": approaches,
                    "current_phase": traci.trafficlight.getPhase(tl_id),
                    "phase_name": traci.trafficlight.getPhaseName(tl_id),
                    "phase_elapsed": traci.trafficlight.getPhaseDuration(tl_id) - (traci.trafficlight.getNextSwitch(tl_id) - traci.simulation.getTime()),
                    "total_waiting_time": sum(appr["queue_length"] for appr in approaches.values()) # Simplified waiting per junction
                }
            except Exception as e:
                logger.warning(f"Error getting state for junction {tl_id}: {e}")
                
        # Fill in average speed for global metrics
        vehicles = traci.vehicle.getIDList()
        if vehicles:
            speeds = [traci.vehicle.getSpeed(v) for v in vehicles]
            state["global_metrics"]["avg_speed"] = sum(speeds) / len(speeds)
        else:
            state["global_metrics"]["avg_speed"] = 0.0
            
        return state
        
    def set_phase(self, tl_id: str, phase_index: int):
        """Set traffic light to specific phase."""
        if self._is_running:
            traci.trafficlight.setPhase(tl_id, phase_index)
            
    def set_phase_duration(self, tl_id: str, duration: float):
        """Set remaining duration of current phase."""
        if self._is_running:
            traci.trafficlight.setPhaseDuration(tl_id, duration)
            
    def get_metrics(self) -> dict:
        """Get aggregate performance metrics for the simulation run."""
        avg_delay = self.total_waiting_time / max(1, self.total_departed)
        return {
            "avg_delay": avg_delay,
            "total_throughput": self.total_arrived,
            "total_vehicles": self.total_departed,
            "total_waiting_time": self.total_waiting_time,
            "los_grade": self._calculate_los(avg_delay)
        }
        
    def get_traffic_light_info(self, tl_id: str) -> dict:
        """Get detailed traffic light program info."""
        if not self._is_running:
            return {}
            
        program = traci.trafficlight.getProgram(tl_id)
        current_phase = traci.trafficlight.getPhase(tl_id)
        
        return {
            "program_id": program,
            "current_phase": current_phase,
            "next_switch": traci.trafficlight.getNextSwitch(tl_id)
        }
        
    def add_vehicle(self, vehicle_id: str, route_id: str, vehicle_type: str = 'car',
                    depart_speed: str = 'max'):
        """Add a vehicle to the simulation (for emergency vehicle injection)."""
        if self._is_running:
            try:
                traci.vehicle.add(vehicle_id, route_id, typeID=vehicle_type, departSpeed=depart_speed)
            except Exception as e:
                logger.error(f"Failed to add vehicle {vehicle_id}: {e}")
                
    def get_vehicle_data(self, vehicle_id: str) -> dict:
        """Get data for a specific vehicle (position, speed, route)."""
        if not self._is_running:
            return {}
            
        try:
            return {
                "position": traci.vehicle.getPosition(vehicle_id),
                "speed": traci.vehicle.getSpeed(vehicle_id),
                "route": traci.vehicle.getRoute(vehicle_id),
                "road": traci.vehicle.getRoadID(vehicle_id)
            }
        except Exception:
            return {}
            
    def stop(self):
        """Stop SUMO simulation and close TraCI connection."""
        if self._is_running:
            traci.close()
            self._is_running = False
            logger.info("Stopped SUMO simulation.")
            
    def reset(self):
        """Reset simulation (stop and restart)."""
        self.stop()
        self.start()
        
    @property
    def is_running(self) -> bool:
        return self._is_running
        
    def _calculate_los(self, avg_delay: float) -> str:
        """Calculate Level of Service grade from average delay.
        IRC:106-1990 / HCM delay-based LOS:
        A: <= 10s, B: 10-20s, C: 20-35s, D: 35-55s, E: 55-80s, F: > 80s
        """
        if avg_delay <= 10:
            return "A"
        elif avg_delay <= 20:
            return "B"
        elif avg_delay <= 35:
            return "C"
        elif avg_delay <= 55:
            return "D"
        elif avg_delay <= 80:
            return "E"
        else:
            return "F"
            
    def _get_approach_direction(self, edge_id: str) -> str:
        """Map SUMO edge ID to approach direction (N/E/S/W)."""
        # A simple heuristic based on typical edge naming conventions
        # User needs to ensure proper edge naming during network generation
        lower_id = edge_id.lower()
        if 'n' in lower_id: return 'N'
        if 's' in lower_id: return 'S'
        if 'e' in lower_id: return 'E'
        if 'w' in lower_id: return 'W'
        return 'N'  # Default fallback
