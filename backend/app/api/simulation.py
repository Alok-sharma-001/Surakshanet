import os
import shutil
import asyncio
import logging
import random
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

try:
    from simulation.sumo_env import SumoEnvironment
    from simulation.scenarios.demand_profiles import get_profile
except ImportError:
    SumoEnvironment = None
    def get_profile(name): return {}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulation", tags=["Simulation"])

class MicroSimRunner:
    """Resilient integrated corridor micro-simulator when TraCI/SUMO binary is unavailable."""
    def __init__(self, scenario: str = "morning_peak"):
        self.scenario = scenario
        self.is_running = False
        self.step_count = 0
        self.sim_time_s = 0
        self.total_vehicles = 1240
        self.avg_speed = 31.4
        self.throughput = 850
        self.avg_delay = 18.2
        self.queue_length = 24.0

    def start(self):
        self.is_running = True
        self.step_count = 0
        self.sim_time_s = 0
        self.total_vehicles = 800 if "off" in self.scenario else 1350

    def step(self, steps: int = 1) -> Dict[str, Any]:
        self.step_count += steps
        self.sim_time_s += steps * 1.0

        # Simulate dynamic variations
        delta_v = random.randint(-5, 8) * steps
        self.total_vehicles = max(200, self.total_vehicles + delta_v)
        self.throughput = round(700 + (self.total_vehicles * 0.25) + random.uniform(-20, 20), 1)
        self.avg_speed = round(max(10.0, min(55.0, 42.0 - (self.total_vehicles / 60.0) + random.uniform(-1.5, 1.5))), 1)
        self.avg_delay = round(max(5.0, min(60.0, 12.0 + (self.total_vehicles / 80.0))), 1)
        self.queue_length = round(max(2.0, (self.total_vehicles / 40.0) + random.uniform(-3, 3)), 1)

        hours = int(self.sim_time_s // 3600)
        mins = int((self.sim_time_s % 3600) // 60)
        secs = int(self.sim_time_s % 60)
        time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

        return {
            "step": self.step_count,
            "sim_time": time_str,
            "vehicles": self.total_vehicles,
            "throughput": self.throughput,
            "avg_speed": self.avg_speed,
            "avg_delay": self.avg_delay,
            "queue_length": self.queue_length,
            "running": self.is_running
        }

    def get_state(self) -> Dict[str, Any]:
        hours = int(self.sim_time_s // 3600)
        mins = int((self.sim_time_s % 3600) // 60)
        secs = int(self.sim_time_s % 60)
        time_str = f"{hours:02d}:{mins:02d}:{secs:02d}"

        return {
            "running": self.is_running,
            "step": self.step_count,
            "sim_time": time_str,
            "scenario": self.scenario,
            "vehicles": self.total_vehicles,
            "avg_speed": self.avg_speed,
            "throughput": self.throughput,
            "queue_length": self.queue_length
        }

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "throughput": self.throughput,
            "avg_delay": self.avg_delay,
            "avg_speed": self.avg_speed,
            "total_vehicles": self.total_vehicles,
            "queue_length": self.queue_length
        }

    def stop(self):
        self.is_running = False

    def reset(self):
        self.is_running = False
        self.step_count = 0
        self.sim_time_s = 0

# Global simulation instance and lock
sim_instance = None
sim_mode = "microsim"  # "sumo" or "microsim"
sim_lock = asyncio.Lock()
active_websockets: List[WebSocket] = []

class StartSimulationRequest(BaseModel):
    scenario_profile: str = "morning_peak"
    net_file: str = "corridor.net.xml"
    route_file: str = "corridor.rou.xml"

class StepRequest(BaseModel):
    steps: int = 1

async def broadcast_state(state: dict):
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json(state)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)

@router.post("/start")
async def start_simulation(req: StartSimulationRequest):
    global sim_instance, sim_mode
    async with sim_lock:
        if sim_instance and getattr(sim_instance, "is_running", False):
            raise HTTPException(status_code=400, detail="Simulation already running")

        has_sumo = shutil.which("sumo") is not None or os.path.exists("/usr/bin/sumo")
        if has_sumo and SumoEnvironment:
            try:
                sim_instance = SumoEnvironment(
                    net_file=req.net_file,
                    route_file=req.route_file,
                    gui=False
                )
                sim_instance.start()
                sim_mode = "sumo"
                return {"status": "started", "engine": "sumo_traci", "scenario": req.scenario_profile}
            except Exception as e:
                logger.warning(f"SUMO TraCI startup failed ({e}). Falling back to MicroSim engine.")

        sim_instance = MicroSimRunner(scenario=req.scenario_profile)
        sim_instance.start()
        sim_mode = "microsim"
        return {"status": "started", "engine": "microsim_driver", "scenario": req.scenario_profile}

@router.post("/step")
async def step_simulation(req: StepRequest, background_tasks: BackgroundTasks):
    global sim_instance
    async with sim_lock:
        if not sim_instance or not getattr(sim_instance, "is_running", False):
            raise HTTPException(status_code=400, detail="Simulation not running")

        state = sim_instance.step(req.steps)
        background_tasks.add_task(broadcast_state, state)
        return {"status": "stepped", "state": state}

@router.get("/state")
@router.get("/status")
async def get_state():
    global sim_instance
    if not sim_instance or not getattr(sim_instance, "is_running", False):
        return {"running": False, "step": 0, "sim_time": "00:00:00", "vehicles": 0}
    return sim_instance.get_state()

@router.post("/stop")
async def stop_simulation():
    global sim_instance
    async with sim_lock:
        if not sim_instance or not getattr(sim_instance, "is_running", False):
            return {"status": "stopped", "running": False}
        sim_instance.stop()
        return {"status": "stopped"}

@router.get("/metrics")
async def get_metrics():
    global sim_instance
    if not sim_instance or not getattr(sim_instance, "is_running", False):
        return {"throughput": 0, "avg_delay": 0, "avg_speed": 0, "total_vehicles": 0}
    return sim_instance.get_metrics()

@router.post("/reset")
async def reset_simulation():
    global sim_instance
    async with sim_lock:
        if sim_instance:
            sim_instance.reset()
        return {"status": "reset"}

@router.websocket("/ws")
async def simulation_ws(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
