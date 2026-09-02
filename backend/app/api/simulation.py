import asyncio
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from simulation.sumo_env import SumoEnvironment
from simulation.scenarios.demand_profiles import get_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulation", tags=["Simulation"])

# Global simulation instance and lock
sim_env = None
sim_lock = asyncio.Lock()

active_websockets = []

class StartSimulationRequest(BaseModel):
    scenario_profile: str = "morning_peak"
    net_file: str = "corridor.net.xml"
    route_file: str = "corridor.rou.xml"

class StepRequest(BaseModel):
    steps: int = 1

async def broadcast_state(state: dict):
    """Broadcast state to all connected websockets."""
    disconnected = []
    for ws in active_websockets:
        try:
            await ws.send_json(state)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        active_websockets.remove(ws)

@router.post("/start")
async def start_simulation(req: StartSimulationRequest):
    global sim_env
    async with sim_lock:
        if sim_env and sim_env.is_running:
            raise HTTPException(status_code=400, detail="Simulation already running")
            
        profile = get_profile(req.scenario_profile)
        
        sim_env = SumoEnvironment(
            net_file=req.net_file,
            route_file=req.route_file,
            gui=False
        )
        
        try:
            sim_env.start()
            return {"status": "started", "scenario": req.scenario_profile}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/step")
async def step_simulation(req: StepRequest, background_tasks: BackgroundTasks):
    global sim_env
    async with sim_lock:
        if not sim_env or not sim_env.is_running:
            raise HTTPException(status_code=400, detail="Simulation not running")
            
        try:
            state = sim_env.step(req.steps)
            background_tasks.add_task(broadcast_state, state)
            return {"status": "stepped", "state": state}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/state")
async def get_state():
    global sim_env
    if not sim_env or not sim_env.is_running:
        raise HTTPException(status_code=400, detail="Simulation not running")
    return sim_env.get_state()

@router.post("/stop")
async def stop_simulation():
    global sim_env
    async with sim_lock:
        if not sim_env or not sim_env.is_running:
            raise HTTPException(status_code=400, detail="Simulation not running")
        sim_env.stop()
        return {"status": "stopped"}

@router.get("/metrics")
async def get_metrics():
    global sim_env
    if not sim_env or not sim_env.is_running:
        raise HTTPException(status_code=400, detail="Simulation not running")
    return sim_env.get_metrics()

@router.post("/reset")
async def reset_simulation():
    global sim_env
    async with sim_lock:
        if not sim_env or not sim_env.is_running:
            raise HTTPException(status_code=400, detail="Simulation not running")
        sim_env.reset()
        return {"status": "reset"}

@router.websocket("/ws")
async def simulation_ws(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Just keep connection open
    except WebSocketDisconnect:
        active_websockets.remove(websocket)
