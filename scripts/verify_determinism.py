#!/usr/bin/env python3
"""SN-127/SN-142: `make verify-determinism`.

Runs each of the five demo scenarios' SUMO route file twice, back to back,
under DEMO_SEED (42), and asserts the resulting metrics are byte-identical.
A demo that behaves differently each rehearsal fails on stage — this is the
single automated guard against that class of regression.

Does not use services/control_service/ab_runner.py (that module's own
`scenario` parameter is decorative — always runs corridor.sumocfg regardless
of the value passed — and CLAUDE.md §14 flags it HIGH-risk / "never adjust
to produce a more favorable number"; extending its scope is out of bounds
for this check). Instead this script drives TraCI directly against each
scenario's real net/route files, exactly as
`backend/app/api/simulation.py::start_simulation` resolves them.

Exit code 0 and "ALL 5 SCENARIOS DETERMINISTIC" when every scenario's two
runs match; exit code 1 and a diff of the first mismatch otherwise.
"""
import json
import os
import shutil
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.sumo_bootstrap import ensure_sumo_on_path
from shared.constants import DEMO_SEED
from simulation.scenarios.demo_scenarios import load_scenarios

NETWORKS_DIR = os.path.join(_REPO_ROOT, "simulation", "networks")
DET_FILE = os.path.join(NETWORKS_DIR, "corridor.det.xml")
CHECK_DURATION_S = 300  # matches every scenario config's duration_s


def run_once(net_file: str, route_file: str, seed: int, end_s: int) -> dict:
    ensure_sumo_on_path()
    import traci

    net_path = os.path.join(NETWORKS_DIR, net_file)
    route_path = os.path.join(NETWORKS_DIR, route_file)

    cmd = [
        "sumo",
        "-n", net_path,
        "-r", route_path,
        "-a", DET_FILE,
        "--seed", str(seed),
        "--random", "false",
        "-b", "0",
        "-e", str(end_s),
        "--step-length", "1.0",
        "--no-warnings", "true",
        "--waiting-time-memory", "10000",
        "--no-step-log", "true",
    ]
    traci.start(cmd)

    total_waiting = 0.0
    total_departed = 0
    total_arrived = 0
    vehicle_speed_sum = 0.0
    vehicle_speed_samples = 0

    try:
        while traci.simulation.getTime() < end_s:
            traci.simulationStep()
            total_departed += traci.simulation.getDepartedNumber()
            total_arrived += traci.simulation.getArrivedNumber()
            for veh_id in traci.vehicle.getIDList():
                total_waiting += traci.vehicle.getWaitingTime(veh_id)
                vehicle_speed_sum += traci.vehicle.getSpeed(veh_id)
                vehicle_speed_samples += 1
    finally:
        traci.close()

    return {
        "total_departed": total_departed,
        "total_arrived": total_arrived,
        # Rounded: SUMO's own floating point accumulation is bit-stable
        # run-to-run at a fixed seed, but rounding keeps this check robust
        # to harmless platform-level float formatting differences rather
        # than actual nondeterminism.
        "total_waiting_time": round(total_waiting, 3),
        "vehicle_speed_sum": round(vehicle_speed_sum, 3),
        "vehicle_speed_samples": vehicle_speed_samples,
    }


def main() -> int:
    if not shutil.which("sumo") and not os.path.exists("/usr/bin/sumo"):
        print("SUMO binary not found — cannot verify determinism.", file=sys.stderr)
        return 1
    try:
        import traci  # noqa: F401
    except ImportError as e:
        print(f"TraCI not importable: {e}", file=sys.stderr)
        return 1

    scenarios = load_scenarios()
    if not scenarios:
        print("Scenario registry (simulation/scenarios/demo_*.json) failed to load.", file=sys.stderr)
        return 1

    failures = []
    for scenario_id in sorted(scenarios):
        config = scenarios[scenario_id]
        net_file = config["net_file"]
        route_file = config["route_file"]
        print(f"Scenario {scenario_id} ({config['name']}): {route_file}, seed {DEMO_SEED} ...", flush=True)

        run_1 = run_once(net_file, route_file, DEMO_SEED, CHECK_DURATION_S)
        run_2 = run_once(net_file, route_file, DEMO_SEED, CHECK_DURATION_S)

        if run_1 == run_2:
            print(f"  OK — deterministic ({json.dumps(run_1)})")
        else:
            print(f"  MISMATCH:\n    run 1: {run_1}\n    run 2: {run_2}")
            failures.append(scenario_id)

    print()
    if failures:
        print(f"FAILED: non-deterministic scenario(s): {', '.join(failures)}", file=sys.stderr)
        return 1

    print(f"ALL {len(scenarios)} SCENARIOS DETERMINISTIC (seed {DEMO_SEED})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
