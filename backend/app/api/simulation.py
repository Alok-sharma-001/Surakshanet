import os
import shutil
import asyncio
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

try:
    from simulation.sumo_env import SumoEnvironment
    from simulation.scenarios.demand_profiles import get_profile
    from shared.paths import resolve_repo_path
except ImportError:
    SumoEnvironment = None
    resolve_repo_path = None
    def get_profile(name): return {}

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/simulation", tags=["Simulation"])


# SN-005: the random-number fallback runner was removed here.
#
# It produced vehicles, speed, delay and queue values from random.randint /
# random.uniform and returned them through the same response shape as real SUMO
# output, so a caller could not tell measured data from invented data. It ran
# whenever SUMO or TraCI was unreachable, which is exactly when the honest answer
# is that no simulation is available.
#
# There is no fallback engine now. When SUMO is unavailable these endpoints
# return 503 with a reason.


def _sumo_available() -> bool:
    """True when both the SUMO binary and the TraCI bindings are usable."""
    if SumoEnvironment is None:
        return False
    return shutil.which("sumo") is not None or os.path.exists("/usr/bin/sumo")


def _unavailable(reason: str) -> HTTPException:
    """The single unavailable response for this router. Never a fabricated value."""
    return HTTPException(
        status_code=503,
        detail={"status": "simulation_unavailable", "reason": reason},
    )


import json
import redis.asyncio as aioredis
from app.config import get_settings
from app.websocket.manager import manager

settings = get_settings()

# Local simulation instance cache and lock
sim_instance = None
sim_mode = "sumo"
sim_lock = asyncio.Lock()


async def get_redis_client():
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_redis_sim_state() -> Optional[Dict[str, Any]]:
    try:
        r = await get_redis_client()
        raw = await r.get("simulation:state")
        await r.aclose()
        if raw:
            return json.loads(raw)
    except Exception as e:
        logger.debug(f"Redis sim state read fallback: {e}")
    return None


async def set_redis_sim_state(state: Dict[str, Any]):
    try:
        r = await get_redis_client()
        await r.set("simulation:state", json.dumps(state))
        if state.get("running"):
            await r.set("simulation:running", "true")
        else:
            await r.set("simulation:running", "false")
        await r.aclose()
    except Exception as e:
        logger.debug(f"Redis sim state write fallback: {e}")


class StartSimulationRequest(BaseModel):
    scenario_profile: str = "morning_peak"
    scenario: Optional[str] = None
    duration: Optional[int] = Field(None, ge=0)
    net_file: str = "corridor.net.xml"
    route_file: str = "corridor.rou.xml"

    def model_post_init(self, __context):
        if self.scenario is not None:
            self.scenario_profile = self.scenario


class StepRequest(BaseModel):
    steps: int = 1


async def broadcast_state(state: dict):
    await manager.broadcast("simulation", state)
    await manager.broadcast("traffic", state)


@router.post("/start")
async def start_simulation(req: StartSimulationRequest):
    global sim_instance, sim_mode
    async with sim_lock:
        redis_state = await get_redis_sim_state()
        is_running = (sim_instance and getattr(sim_instance, "is_running", False)) or (redis_state and redis_state.get("running"))
        if is_running:
            raise HTTPException(status_code=409, detail="Simulation already running")

        if not _sumo_available():
            raise _unavailable(
                "SUMO binary or TraCI bindings not available on this host. "
                "See docs/04-environment-setup.md."
            )

        try:
            NET_DIR_PARTS = ("simulation", "networks")
            if resolve_repo_path:
                net_path = resolve_repo_path(*NET_DIR_PARTS, req.net_file) or req.net_file
                route_path = resolve_repo_path(*NET_DIR_PARTS, req.route_file) or req.route_file
                det_path = resolve_repo_path(*NET_DIR_PARTS, "corridor.det.xml")
            else:
                net_path = req.net_file
                route_path = req.route_file
                det_path = None

            sim_instance = SumoEnvironment(
                net_file=net_path,
                route_file=route_path,
                additional_files=[det_path] if det_path else None,
                gui=False
            )
            sim_instance.start()
            sim_mode = "sumo"
            initial_state = {"running": True, "step": 0, "scenario": req.scenario_profile, "engine": "sumo_traci"}
            await set_redis_sim_state(initial_state)
            return {"status": "started", "engine": "sumo_traci", "scenario": req.scenario_profile}
        except Exception as e:
            # SN-005: previously fell back to the RNG engine here.
            logger.error(f"SUMO TraCI startup failed: {e}")
            sim_instance = None
            raise _unavailable(f"SUMO failed to start: {e}")


@router.post("/step")
async def step_simulation(req: StepRequest, background_tasks: BackgroundTasks):
    global sim_instance
    async with sim_lock:
        redis_state = await get_redis_sim_state()
        is_running = (sim_instance and getattr(sim_instance, "is_running", False)) or (redis_state and redis_state.get("running"))
        if not is_running:
            raise HTTPException(status_code=400, detail="Simulation not running")

        # SN-005: previously rebuilt a mock fallback runner from cached Redis values
        # when this worker held no live handle, which resumed a *different*,
        # invented simulation. A worker without the TraCI connection cannot step
        # the simulation and now says so.
        if not sim_instance or not getattr(sim_instance, "is_running", False):
            raise _unavailable(
                "This worker holds no live SUMO connection. Step requests must "
                "reach the worker that started the simulation."
            )

        state = sim_instance.step(req.steps)
        await set_redis_sim_state(state)
        background_tasks.add_task(broadcast_state, state)
        return {"status": "stepped", "state": state}


@router.get("/state")
@router.get("/status")
async def get_state():
    global sim_instance
    if sim_instance and getattr(sim_instance, "is_running", False):
        return sim_instance.get_state()

    redis_state = await get_redis_sim_state()
    if redis_state and redis_state.get("running"):
        return redis_state

    # SN-005: distinguish "SUMO is here, nothing started" from "no simulation
    # engine at all". The second is a 503; it is not reported as an idle
    # simulation, because there is no simulation.
    if not _sumo_available():
        raise _unavailable("SUMO binary or TraCI bindings not available on this host.")

    return {"running": False, "step": 0, "sim_time": "00:00:00", "vehicles": 0, "source": "sumo"}


@router.post("/stop")
async def stop_simulation():
    global sim_instance
    async with sim_lock:
        if sim_instance:
            sim_instance.stop()

        stopped_state = {"running": False, "status": "stopped"}
        await set_redis_sim_state(stopped_state)
        return {"status": "stopped", "running": False}


@router.get("/metrics")
async def get_metrics():
    global sim_instance
    if sim_instance and getattr(sim_instance, "is_running", False):
        return sim_instance.get_metrics()

    redis_state = await get_redis_sim_state()
    if redis_state and redis_state.get("running"):
        return {
            "throughput": redis_state.get("throughput"),
            "avg_delay": redis_state.get("avg_delay"),
            "avg_speed": redis_state.get("avg_speed"),
            "total_vehicles": redis_state.get("vehicles"),
            "queue_length": redis_state.get("queue_length"),
            "source": "sumo",
        }

    # SN-005: previously returned zeros, which render as a real reading of zero
    # traffic. No running simulation means no metrics.
    raise _unavailable("No simulation is running, so there are no metrics to report.")


@router.post("/reset")
async def reset_simulation():
    global sim_instance
    async with sim_lock:
        if sim_instance:
            sim_instance.reset()
        try:
            r = await get_redis_client()
            await r.delete("simulation:state", "simulation:running")
            await r.aclose()
        except Exception:
            pass
        return {"status": "reset"}


@router.websocket("/ws")
async def simulation_ws(websocket: WebSocket):
    await manager.connect(websocket, "simulation")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, "simulation")
