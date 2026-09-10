"""
SurakshaNet A/B Proof Harness (SN-038)
=====================================
Executes dual simulation runs comparing:
- Arm A: Fixed-time Webster baseline
- Arm B: Deep Q-Network MARL agent

Both arms execute under:
- Identical network, routes, and demand profile
- Identical seed (DEMO_SEED = 42 default)
- Identical step length and duration
- The exact SAME safety envelope outside the policy

Computes improvement percentages strictly per docs/08-marl-control.md §7.
"""

import logging
import os
import shutil
import uuid
from typing import Dict, Any, Optional, Tuple

from services.control_service.config import ControlConfig, WEIGHTS_PATH
from services.control_service.controllers import MarlController, WebsterController
from services.control_service.safety import SafetyEnvelope, JunctionRuntimeState
from services.control_service.state import build_state_vector
from shared.constants import DataSource
from shared.paths import resolve_repo_path
from shared.sumo_bootstrap import ensure_sumo_on_path

logger = logging.getLogger("surakshanet.ab_runner")

DEMO_SEED = 42


def compute_ab_improvement(
    arm_a_metrics: Dict[str, float],
    arm_b_metrics: Dict[str, float]
) -> Dict[str, float]:
    """
    Computes improvement percentages between Webster (Arm A) and MARL (Arm B).
    Conforms to docs/08-marl-control.md §7:

    Cost metrics (lower is better: delay, queue, wait, travel time):
        improvement_pct = (arm_a - arm_b) / arm_a * 100

    Benefit metrics (higher is better: throughput, vehicles served):
        improvement_pct = (arm_b - arm_a) / arm_a * 100
    """
    cost_metrics = {
        "avg_delay_s",
        "total_delay_s",
        "avg_queue_pcu",
        "avg_wait_s",
        "avg_travel_time_s"
    }
    benefit_metrics = {
        "throughput_veh_h",
        "vehicles_served"
    }

    improvements = {}
    for metric, val_a in arm_a_metrics.items():
        if metric not in arm_b_metrics:
            continue
        val_b = arm_b_metrics[metric]
        if val_a is None or val_b is None:
            continue

        val_a = float(val_a)
        val_b = float(val_b)

        if val_a == 0.0:
            pct = 0.0
        elif metric in cost_metrics:
            pct = ((val_a - val_b) / val_a) * 100.0
        elif metric in benefit_metrics:
            pct = ((val_b - val_a) / val_a) * 100.0
        else:
            pct = ((val_a - val_b) / val_a) * 100.0

        improvements[f"{metric}_pct"] = round(float(pct), 2)

    return improvements


def generate_ab_statement(
    scenario: str,
    seed: int,
    duration_s: int,
    arm_a: Dict[str, float],
    arm_b: Dict[str, float],
    improvement: Dict[str, float]
) -> str:
    """
    Generates human-readable evidence statement.
    Rule R7: If DQN performed worse, report it honestly without embellishment.
    """
    delay_imp = improvement.get("avg_delay_s_pct", 0.0)
    vehicles = int(arm_b.get("vehicles_served", 0))

    if delay_imp >= 0:
        return (
            f'AI reduced average delay by {delay_imp:.1f}% vs fixed-time under '
            f'Scenario "{scenario}" (seed {seed}, {duration_s} s, {vehicles} vehicles).'
        )
    else:
        return (
            f'AI increased average delay by {abs(delay_imp):.1f}% vs fixed-time under '
            f'Scenario "{scenario}" (seed {seed}, {duration_s} s, {vehicles} vehicles).'
        )


class ABRunner:
    def __init__(self, weights_path: str = WEIGHTS_PATH):
        self.weights_path = weights_path
        self.cfg = ControlConfig(weights_path=weights_path)
        self.envelope = SafetyEnvelope(self.cfg)

    def run_arm(
        self,
        controller_type: str,
        seed: int,
        duration_s: int,
        scenario: str = "surge"
    ) -> Dict[str, float]:
        """
        Runs one arm of the simulation under TraCI using the specified controller.
        """
        ensure_sumo_on_path()
        try:
            import traci
        except ImportError as e:
            raise RuntimeError(f"TraCI unimportable in interpreter {sys.executable}: {e}")

        sumo_bin = shutil.which("sumo")
        if not sumo_bin:
            raise RuntimeError("SUMO binary not found on PATH.")

        cfg_path = resolve_repo_path("simulation", "networks", "corridor.sumocfg")
        if not cfg_path:
            raise RuntimeError("Could not find corridor.sumocfg.")

        # Initialize controller
        if controller_type == "marl":
            controller = MarlController(self.weights_path)
            if not controller.is_loaded:
                raise RuntimeError("MARL weights not loaded; cannot run MARL arm.")
        else:
            controller = WebsterController()

        label = f"ab_{controller_type}_{seed}_{uuid.uuid4().hex[:6]}"
        cmd = [
            sumo_bin,
            "-c", cfg_path,
            "--seed", str(seed),
            "--random", "false",
            "-b", "0",
            "-e", str(duration_s),
            "--step-length", "1.0",
            "--no-warnings", "true",
            "--duration-log.disable", "true",
            "--waiting-time-memory", "10000"
        ]

        traci.start(cmd, label=label)
        conn = traci.getConnection(label)

        tl_ids = list(conn.trafficlight.getIDList())
        all_dets = set(conn.lanearea.getIDList())

        # Metric tracking
        departed_times: Dict[str, float] = {}
        travel_times: list[float] = []
        total_waiting_seconds = 0.0
        queue_samples: list[float] = []
        all_seen_vehicles = set()
        total_arrived = 0

        # Junction states for safety envelope
        phase_start_times: Dict[str, float] = {tl: 0.0 for tl in tl_ids}
        last_phases: Dict[str, int] = {tl: 0 for tl in tl_ids}
        cycles_since_ped: Dict[str, int] = {tl: 0 for tl in tl_ids}
        for tl in tl_ids:
            conn.trafficlight.setPhaseDuration(tl, 999.0)

        try:
            for step in range(duration_s):
                sim_time = float(conn.simulation.getTime())

                # Track departures & arrivals
                departed_now = conn.simulation.getDepartedIDList()
                for vid in departed_now:
                    departed_times[vid] = sim_time
                    all_seen_vehicles.add(vid)

                arrived_now = conn.simulation.getArrivedIDList()
                total_arrived += len(arrived_now)
                for vid in arrived_now:
                    if vid in departed_times:
                        travel_times.append(sim_time - departed_times[vid])

                # Accumulate waiting time for active vehicles
                active_vehicles = conn.vehicle.getIDList()
                for vid in active_vehicles:
                    all_seen_vehicles.add(vid)
                    total_waiting_seconds += float(conn.vehicle.getWaitingTime(vid))

                # Sample detector queues
                step_queue_pcu = 0.0
                for det in all_dets:
                    jam_m = float(conn.lanearea.getJamLengthMeters(det))
                    step_queue_pcu += (jam_m / 5.5)
                queue_samples.append(step_queue_pcu)

                # Control decision step every 5 seconds
                if step > 0 and step % int(self.cfg.control_step_s) == 0:
                    for tl in tl_ids:
                        curr_phase = conn.trafficlight.getPhase(tl)
                        if curr_phase != last_phases[tl]:
                            last_phases[tl] = curr_phase
                            phase_start_times[tl] = sim_time

                        phase_elapsed = max(0.0, sim_time - phase_start_times[tl])

                        # Build basic approach info for decision
                        approaches = []
                        from shared.telemetry import ApproachTelemetry, JunctionTelemetry
                        for d in ["N", "E", "S", "W"]:
                            det_id = f"det_{tl}_{d}_0"
                            if det_id in all_dets:
                                v_count = float(conn.lanearea.getLastStepVehicleNumber(det_id))
                                jam_m = float(conn.lanearea.getJamLengthMeters(det_id))
                                spd = max(0.0, float(conn.lanearea.getLastStepMeanSpeed(det_id)) * 3.6)
                                occ = max(0.0, min(1.0, float(conn.lanearea.getLastStepOccupancy(det_id)) / 100.0))
                                approaches.append(ApproachTelemetry(
                                    direction=d, lane_ids=[], vehicle_count=v_count, pcu=v_count,
                                    queue_length_m=jam_m, mean_speed_kmh=spd, occupancy=occ,
                                    accumulated_wait_s=0.0
                                ))
                            else:
                                approaches.append(ApproachTelemetry(
                                    direction=d, lane_ids=[], vehicle_count=0.0, pcu=0.0,
                                    queue_length_m=0.0, mean_speed_kmh=35.0, occupancy=0.0,
                                    accumulated_wait_s=0.0
                                ))

                        telemetry = JunctionTelemetry(
                            junction_id=tl,
                            source=DataSource.SUMO,
                            approaches=approaches,
                            current_phase=curr_phase,
                            phase_elapsed_s=phase_elapsed,
                            sim_time_s=sim_time
                        )
                        s_res = build_state_vector(telemetry, self.cfg)

                        # Inference
                        dec = controller.select_action(
                            junction_id=tl,
                            state_vector=s_res.numpy_vector,
                            current_phase=curr_phase,
                            phase_elapsed_s=phase_elapsed
                        )

                        # Enforce identical safety envelope on both arms!
                        runtime_state = JunctionRuntimeState(
                            junction_id=tl,
                            current_phase=curr_phase,
                            phase_elapsed_s=phase_elapsed,
                            cycles_since_pedestrian_phase=cycles_since_ped[tl]
                        )
                        safety_res = self.envelope.evaluate(dec.action, runtime_state)

                        if safety_res.applied_phase != curr_phase:
                            conn.trafficlight.setPhase(tl, safety_res.applied_phase)
                            if safety_res.applied_phase == 2:
                                cycles_since_ped[tl] = 0
                            elif safety_res.applied_phase == 0 and last_phases[tl] == 3:
                                cycles_since_ped[tl] += 1
                            phase_start_times[tl] = sim_time
                            last_phases[tl] = safety_res.applied_phase
                            conn.trafficlight.setPhaseDuration(tl, safety_res.applied_duration_s)
                        else:
                            conn.trafficlight.setPhaseDuration(tl, 999.0)

                conn.simulationStep()

        finally:
            conn.close()

        # Compute arm summary metrics
        total_veh = max(1, len(all_seen_vehicles))
        avg_delay = total_waiting_seconds / total_veh
        avg_queue = (sum(queue_samples) / len(queue_samples)) if queue_samples else 0.0
        avg_wait = total_waiting_seconds / max(1, total_arrived) if total_arrived > 0 else avg_delay
        avg_travel = (sum(travel_times) / len(travel_times)) if travel_times else 0.0
        throughput = total_arrived / (duration_s / 3600.0)

        return {
            "avg_delay_s": round(avg_delay, 2),
            "total_delay_s": round(total_waiting_seconds, 2),
            "avg_queue_pcu": round(avg_queue, 2),
            "avg_wait_s": round(avg_wait, 2),
            "throughput_veh_h": round(throughput, 1),
            "avg_travel_time_s": round(avg_travel, 2),
            "vehicles_served": total_arrived
        }

    def run_ab_comparison(
        self,
        scenario: str = "surge",
        seed: int = DEMO_SEED,
        duration_s: int = 900
    ) -> Dict[str, Any]:
        """
        Executes dual simulation runs (Arm A Webster, Arm B MARL) and computes improvements.
        """
        logger.info(f"Running A/B Comparison: Scenario={scenario}, Seed={seed}, Duration={duration_s}s")

        logger.info("Executing Arm A (Webster Baseline)...")
        arm_a = self.run_arm("webster", seed=seed, duration_s=duration_s, scenario=scenario)

        logger.info("Executing Arm B (MARL DQN Policy)...")
        arm_b = self.run_arm("marl", seed=seed, duration_s=duration_s, scenario=scenario)

        improvement = compute_ab_improvement(arm_a, arm_b)
        statement = generate_ab_statement(scenario, seed, duration_s, arm_a, arm_b, improvement)

        return {
            "scenario": scenario,
            "seed": seed,
            "duration_s": duration_s,
            "arm_a_controller": "webster",
            "arm_b_controller": "marl",
            "arm_a_metrics": arm_a,
            "arm_b_metrics": arm_b,
            "improvement": improvement,
            "statement": statement,
            "status": "complete"
        }
