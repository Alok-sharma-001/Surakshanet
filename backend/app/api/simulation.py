import os
import shutil
import asyncio
import logging
import time
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.models.user import User
from app.services.auth_service import require_role

try:
    from simulation.sumo_env import SumoEnvironment
    from simulation.scenarios.demand_profiles import get_profile
    from simulation.scenarios.demo_scenarios import get_scenario, load_scenarios
    from shared.paths import resolve_repo_path
except ImportError:
    SumoEnvironment = None
    resolve_repo_path = None
    def get_profile(name): return {}
    def get_scenario(scenario_id): return None
    def load_scenarios(): return {}

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
from shared.constants import REDIS_CHANNELS

settings = get_settings()

# Local simulation instance cache and lock
sim_instance = None
sim_mode = "sumo"
sim_lock = asyncio.Lock()
# Set once in start_simulation; SumoEnvironment.get_state() itself has no
# concept of "which named scenario" or "which seed" — it's a generic SUMO
# wrapper — so the scenario switcher's display (SN-133: "displays scenario,
# seed and elapsed sim time") reads this alongside the live TraCI state.
sim_scenario_info: Dict[str, Any] = {}
# Real measurements of the sandbox's own health, not an assumption that
# running=True means it is actually advancing. Set on every successful step
# (manual or auto); read by /state so a hijacked or crashed TraCI connection
# (e.g. services/control_service/ab_runner.py's labeled traci.start() rebinds
# the module-level connection SumoEnvironment's bare traci calls depend on)
# presents as "has not advanced for Ns", not a silently frozen step count.
_sim_last_advanced_monotonic: Optional[float] = None
_sim_fault: Optional[str] = None


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
    scenario_id: Optional[str] = None
    duration: Optional[int] = Field(None, ge=0)
    net_file: str = "corridor.net.xml"
    route_file: str = "corridor.rou.xml"

    def model_post_init(self, __context):
        if self.scenario is not None:
            self.scenario_profile = self.scenario


class StepRequest(BaseModel):
    steps: int = 1


async def broadcast_state(state: dict):
    # This is this API process's own private sandbox SUMO (PATH 2), a
    # completely separate simulation from simulation/sumo_live_bridge.py
    # (PATH 1), which is the process that actually feeds the Live Traffic
    # Map, the control service, and emergency corridors. Broadcasting the
    # sandbox into the bridge-owned "simulation"/"traffic" rooms let
    # TrafficMapPage's isTwinConnected go true from a sandbox scenario while
    # the real bridge was dead — a live fabrication. The sandbox gets its
    # own room, reachable via the existing authenticated /ws/{channel} route.
    await manager.broadcast("simulation_sandbox", state)


@router.get("/scenarios")
async def list_scenarios(current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER"))):
    """SN-133: lists the five demo scenarios from the server-side registry
    (simulation/scenarios/demo_*.json) for the frontend switcher — never a
    hardcoded list in this file, so the registry stays the single source
    of truth this endpoint and /simulation/start's scenario_id both read."""
    scenarios = load_scenarios()
    if not scenarios:
        raise _unavailable("Scenario registry could not be loaded (simulation package unavailable).")
    return {"scenarios": list(scenarios.values())}


@router.post("/start")
async def start_simulation(
    req: StartSimulationRequest,
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    global sim_instance, sim_mode, sim_scenario_info, _sim_last_advanced_monotonic, _sim_fault
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

        net_file = req.net_file
        route_file = req.route_file
        scenario_label = req.scenario_profile
        scenario_config: Optional[Dict[str, Any]] = None

        if req.scenario_id is not None:
            # SN-133: the route/net files for a named scenario come only from
            # the server-side registry, never from the client-supplied
            # net_file/route_file fields — same "don't trust the client for
            # something that must be fixed" pattern already applied to the
            # `role` field in Phase 7. This is also what keeps every scenario
            # deterministic: the registry's files are the only ones a
            # scenario_id can select, and SumoEnvironment's seed always
            # defaults to DEMO_SEED regardless.
            scenario_config = get_scenario(req.scenario_id)
            if scenario_config is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown scenario_id '{req.scenario_id}'. See GET /simulation/scenarios.",
                )
            net_file = scenario_config["net_file"]
            route_file = scenario_config["route_file"]
            scenario_label = scenario_config["id"]

        try:
            NET_DIR_PARTS = ("simulation", "networks")
            if resolve_repo_path:
                net_path = resolve_repo_path(*NET_DIR_PARTS, net_file) or net_file
                route_path = resolve_repo_path(*NET_DIR_PARTS, route_file) or route_file
                det_path = resolve_repo_path(*NET_DIR_PARTS, "corridor.det.xml")
            else:
                net_path = net_file
                route_path = route_file
                det_path = None

            sim_instance = SumoEnvironment(
                net_file=net_path,
                route_file=route_path,
                additional_files=[det_path] if det_path else None,
                gui=False
            )
            sim_instance.start()
            sim_mode = "sumo"
            _sim_last_advanced_monotonic = time.monotonic()
            _sim_fault = None
            sim_scenario_info = {
                "scenario": scenario_label,
                "scenario_id": scenario_config["id"] if scenario_config else None,
                "seed": sim_instance.seed,
            }
            initial_state = {
                "running": True,
                "step": 0,
                "engine": "sumo_traci",
                **sim_scenario_info,
            }
            await set_redis_sim_state(initial_state)
            return {
                "status": "started",
                "engine": "sumo_traci",
                "scenario": scenario_label,
                "scenario_id": scenario_config["id"] if scenario_config else None,
                "seed": sim_instance.seed,
            }
        except Exception as e:
            # SN-005: previously fell back to the RNG engine here.
            logger.error(f"SUMO TraCI startup failed: {e}")
            sim_instance = None
            raise _unavailable(f"SUMO failed to start: {e}")


@router.post("/step")
async def step_simulation(
    req: StepRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
):
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

        global _sim_last_advanced_monotonic, _sim_fault
        state = {**sim_instance.step(req.steps), "running": True, **sim_scenario_info}
        _sim_last_advanced_monotonic = time.monotonic()
        _sim_fault = None
        await set_redis_sim_state(state)
        background_tasks.add_task(broadcast_state, state)
        return {"status": "stepped", "state": state}


@router.get("/state")
@router.get("/status")
async def get_state(current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER"))):
    global sim_instance
    if sim_instance and getattr(sim_instance, "is_running", False):
        step_age_s = (
            time.monotonic() - _sim_last_advanced_monotonic
            if _sim_last_advanced_monotonic is not None else None
        )
        return {
            **sim_instance.get_state(),
            "running": True,
            **sim_scenario_info,
            "step_age_s": round(step_age_s, 2) if step_age_s is not None else None,
            "sandbox_fault": _sim_fault,
        }

    redis_state = await get_redis_sim_state()
    if redis_state and redis_state.get("running"):
        return redis_state

    # SN-005: distinguish "SUMO is here, nothing started" from "no simulation
    # engine at all". The second is a 503; it is not reported as an idle
    # simulation, because there is no simulation.
    if not _sumo_available():
        raise _unavailable("SUMO binary or TraCI bindings not available on this host.")

    # "source" is deliberately absent here, not "sumo": nothing has been
    # measured on this idle row. TelemetrySourceBadge renders UNAVAILABLE for
    # a missing source per its documented no-default behavior; stamping a
    # measured-family value on a row with no measurement is exactly the
    # provenance violation Invariant 13.3 exists to prevent.
    return {"running": False, "step": 0, "sim_time": "00:00:00", "vehicles": 0}


@router.post("/stop")
async def stop_simulation(current_user: User = Depends(require_role("ADMIN", "OPERATOR"))):
    global sim_instance, sim_scenario_info, _sim_last_advanced_monotonic, _sim_fault
    async with sim_lock:
        if sim_instance:
            sim_instance.stop()
        sim_scenario_info = {}
        _sim_last_advanced_monotonic = None
        _sim_fault = None

        stopped_state = {"running": False, "status": "stopped"}
        await set_redis_sim_state(stopped_state)
        return {"status": "stopped", "running": False}


@router.get("/metrics")
async def get_metrics(current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER"))):
    global sim_instance
    if sim_instance and getattr(sim_instance, "is_running", False):
        # SumoEnvironment.get_metrics() only tracks throughput/delay counters
        # (as total_throughput, not throughput) and has no avg_speed field —
        # the dashboard's Simulation page expects throughput/avg_speed/source,
        # which were silently always undefined, rendering as a permanent "—"
        # / "UNAVAILABLE" badge even while the simulation genuinely ran.
        # avg_speed here is a real vehicle-count-weighted average across every
        # approach's measured detector speed (get_state()), not a fabricated
        # value — None (not 0) when no vehicle is present to measure.
        base = sim_instance.get_metrics()
        state = sim_instance.get_state()
        weighted_speed_total = 0.0
        vehicles_with_speed = 0.0
        for junction in state.get("junctions", {}).values():
            for approach in junction.get("approaches", {}).values():
                vc = approach.get("vehicle_count", 0.0)
                if vc > 0:
                    weighted_speed_total += approach["avg_speed"] * vc
                    vehicles_with_speed += vc
        avg_speed = (weighted_speed_total / vehicles_with_speed) if vehicles_with_speed > 0 else None
        return {
            "throughput": base.get("total_throughput"),
            "avg_delay": base.get("avg_delay"),
            "avg_speed": avg_speed,
            "total_vehicles": base.get("total_vehicles"),
            "source": "sumo",
        }

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
async def reset_simulation(current_user: User = Depends(require_role("ADMIN", "OPERATOR"))):
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


async def auto_step_loop():
    """Advances whatever simulation this worker is holding, once per real
    second, at step_length=1.0 (SumoEnvironment's default) so 1 real second
    of wall clock ~= 1 simulated second.

    Before this loop existed, starting a scenario only ever set
    `running: true` — nothing ever called `sim_instance.step()` except a
    manual click on the Simulation page's single-step button, so the
    dashboard's Current Step/Elapsed Sim Time/vehicle counts sat frozen at
    their start-of-run values indefinitely, and switching scenarios looked
    like it did nothing: the new scenario was genuinely running, just never
    advancing. This loop is the real fix — the Step button and
    POST /simulation/step remain available for exact manual control, this
    just means Play now actually plays. Runs only in whichever worker
    process's `sim_instance` global is live (see the --workers 1 demo-profile
    fix in infra/docker-compose.demo.yml); a worker with no running instance
    just no-ops every tick, same as a manual /step request would.
    """
    global _sim_last_advanced_monotonic, _sim_fault
    while True:
        await asyncio.sleep(1.0)
        try:
            async with sim_lock:
                if not sim_instance or not getattr(sim_instance, "is_running", False):
                    continue
                state = {**sim_instance.step(1), "running": True, **sim_scenario_info}
            _sim_last_advanced_monotonic = time.monotonic()
            _sim_fault = None
            await set_redis_sim_state(state)
            await broadcast_state(state)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # A TraCI-level failure (e.g. another process hijacking the
            # module-level connection SumoEnvironment's bare traci calls
            # depend on) must not leave the sandbox silently reporting a
            # frozen-but-confident step count. Record the real fault; do not
            # touch sim_instance.is_running here — /state's step_age_s (based
            # on _sim_last_advanced_monotonic, which this branch does NOT
            # update) is what tells the caller the sandbox has stopped
            # advancing, and sandbox_fault says why.
            _sim_fault = str(e)
            logger.warning(f"Auto-step tick skipped: {e}")


@router.get("/live")
async def get_bridge_live(current_user: User = Depends(require_role("ADMIN", "OPERATOR", "VIEWER"))):
    """Observes simulation/sumo_live_bridge.py (PATH 1) — the process with
    the actual live TraCI connection to the corridor, which also feeds the
    Live Traffic Map, the control service, and emergency corridors. Every
    value is the bridge's last real measurement or None — see
    app/services/bridge_observer.py for the exact staleness rule. The API
    cannot start, stop, or reset this process (it is a host process launched
    by start.sh/stop.sh; this backend runs in a container) or change its
    loaded scenario, but it CAN pause/resume/step its stepping loop — see
    POST /live/pause, /live/resume, /live/step below."""
    from app.services.bridge_observer import observe_bridge
    return await observe_bridge()


async def _publish_bridge_command(cmd: Dict[str, Any]) -> None:
    """Publishes a command to the same Redis channel
    (REDIS_CHANNELS["control_commands"]) simulation/sumo_live_bridge.py
    already subscribes to and safely drains on its own main TraCI thread
    (listen_dashboard_commands queues it; the main loop dispatches it) —
    the identical, already-proven pattern the control service and emergency
    activation use to reach the bridge. No new channel, no new thread."""
    r = await get_redis_client()
    await r.publish(REDIS_CHANNELS["control_commands"], json.dumps(cmd))
    await r.aclose()


async def _require_bridge_reachable() -> None:
    """The bridge's command protocol has no acknowledgement — a command
    published to a bridge that isn't there is silently lost. Refuse before
    sending rather than claim a fire-and-forget success that may never
    happen; GET /simulation/live is the single source of truth this checks."""
    from app.services.bridge_observer import observe_bridge
    live = await observe_bridge()
    if live["status"] not in ("live", "stale"):
        raise _unavailable(
            "No live SUMO bridge to command. See GET /simulation/live."
        )


@router.post("/live/pause")
async def pause_bridge(current_user: User = Depends(require_role("ADMIN", "OPERATOR"))):
    """Requests the live bridge stop advancing TraCI. This is fire-and-forget
    — the bridge has no ack protocol, so the response reports only that the
    command was published, never that it took effect. The bridge keeps
    publishing ticks at its normal cadence while paused (so it never looks
    dead), with run_state: "PAUSED" in GET /simulation/live's response —
    poll that to see the real, applied state."""
    await _require_bridge_reachable()
    await _publish_bridge_command({"type": "SUMO_PAUSE"})
    return {"status": "command_sent", "command": "SUMO_PAUSE"}


@router.post("/live/resume")
async def resume_bridge(current_user: User = Depends(require_role("ADMIN", "OPERATOR"))):
    """Requests the live bridge resume advancing TraCI. Fire-and-forget —
    see pause_bridge's docstring; poll GET /simulation/live's run_state."""
    await _require_bridge_reachable()
    await _publish_bridge_command({"type": "SUMO_RESUME"})
    return {"status": "command_sent", "command": "SUMO_RESUME"}


@router.post("/live/step")
async def step_bridge(
    req: StepRequest,
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
):
    """Requests the live bridge advance exactly `steps` TraCI steps even
    while paused (a running bridge steps continuously already, so this is
    mainly useful while paused for frame-by-frame control). Fire-and-forget
    — see pause_bridge's docstring; poll GET /simulation/live's step."""
    await _require_bridge_reachable()
    await _publish_bridge_command({"type": "SUMO_STEP", "steps": req.steps})
    return {"status": "command_sent", "command": "SUMO_STEP", "steps": req.steps}
