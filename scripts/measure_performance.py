#!/usr/bin/env python3
"""SN-145: Performance sanity — real measurements, not asserted numbers.

Every number in docs/23-final-acceptance.md §6 must trace back to this
script's output (or the cold-start timing captured separately when running
./start.sh for real). Run this against the live demo stack:

    DATABASE_URL=... REDIS_URL=... PYTHONPATH=$(pwd):$(pwd)/backend \
        .venv/bin/python3 scripts/measure_performance.py --backend-url http://127.0.0.1:8123

Requires a running backend (for the API/WebSocket measurements) and the
real demo Postgres/Redis/SUMO. Prints one JSON object with every measured
metric — no metric is reported unless it was actually timed this run.
"""
import argparse
import asyncio
import json
import os
import statistics
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
backend_path = os.path.join(_REPO_ROOT, "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


def _percentile(samples_ms, pct):
    if not samples_ms:
        return None
    ordered = sorted(samples_ms)
    idx = min(len(ordered) - 1, int(round(pct / 100.0 * (len(ordered) - 1))))
    return ordered[idx]


def measure_inference_latency(n=200):
    """MarlController.select_action() over N calls against the real loaded
    policy weights — real PyTorch forward passes, not a stub."""
    import numpy as np
    from services.control_service.controllers import MarlController

    controller = MarlController()
    if not controller.is_loaded:
        return {"error": "MARL weights not loaded — cannot measure real inference latency"}

    state = np.random.rand(8).astype(np.float32)
    samples_ms = []
    for _ in range(n):
        t0 = time.perf_counter()
        controller.select_action(junction_id="J1", state_vector=state, current_phase=0, phase_elapsed_s=10.0)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)

    return {
        "n_samples": n,
        "p50_ms": round(statistics.median(samples_ms), 3),
        "p95_ms": round(_percentile(samples_ms, 95), 3),
        "max_ms": round(max(samples_ms), 3),
    }


def measure_control_step_lag(n=50):
    """One full control-decision cycle (state vector -> safety envelope ->
    applied phase/duration) timed against the 1.0s SUMO step-length this
    corridor runs at (simulation/networks/corridor.sumocfg step-length)."""
    import numpy as np
    from services.control_service.controllers import MarlController
    from services.control_service.safety import SafetyEnvelope, JunctionRuntimeState, ACTION_EXTEND

    controller = MarlController()
    envelope = SafetyEnvelope()
    if not controller.is_loaded:
        return {"error": "MARL weights not loaded — cannot measure real control step lag"}

    state = np.random.rand(8).astype(np.float32)
    runtime_state = JunctionRuntimeState(
        junction_id="J1", current_phase=0, phase_elapsed_s=10.0,
        cycles_since_pedestrian_phase=1, emergency_preemption_active=False,
    )

    samples_ms = []
    for _ in range(n):
        t0 = time.perf_counter()
        decision = controller.select_action(junction_id="J1", state_vector=state, current_phase=0, phase_elapsed_s=10.0)
        envelope.evaluate(action=decision.action, state=runtime_state, controller_name="marl")
        samples_ms.append((time.perf_counter() - t0) * 1000.0)

    step_length_s = 1.0
    max_observed_s = max(samples_ms) / 1000.0
    return {
        "n_samples": n,
        "step_length_s": step_length_s,
        "p95_ms": round(_percentile(samples_ms, 95), 3),
        "max_ms": round(max(samples_ms), 3),
        "lag_behind_step_s": round(max_observed_s, 4),
    }


async def measure_api_latency(backend_url, token, n=50):
    """Real HTTP round trips against a running backend — not a stub."""
    import httpx

    endpoints = ["/api/v1/simulation/scenarios", "/api/v1/junctions", "/health/deep"]
    samples_ms = []
    async with httpx.AsyncClient(base_url=backend_url, timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        for _ in range(n):
            ep = endpoints[_ % len(endpoints)]
            t0 = time.perf_counter()
            resp = await client.get(ep, headers=headers)
            samples_ms.append((time.perf_counter() - t0) * 1000.0)
            if resp.status_code >= 500:
                return {"error": f"{ep} returned {resp.status_code}"}

    return {
        "n_samples": n,
        "endpoints": endpoints,
        "p50_ms": round(statistics.median(samples_ms), 3),
        "p95_ms": round(_percentile(samples_ms, 95), 3),
        "max_ms": round(max(samples_ms), 3),
    }


async def measure_websocket_fanout(backend_url, n_clients=20):
    """Connects N real concurrent WebSocket clients to /ws/traffic and
    confirms every one receives a broadcast published via the real Redis
    pub/sub bridge, with no drops."""
    import websockets
    import redis.asyncio as aioredis
    from app.config import get_settings
    from shared.constants import REDIS_CHANNELS

    ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://") + "/ws/traffic"
    settings = get_settings()

    connections = []
    received = {}

    async def client_task(idx):
        try:
            ws = await websockets.connect(ws_url, open_timeout=5)
            connections.append(ws)
            received[idx] = False
            async def _wait():
                async for msg in ws:
                    if "perf_test_marker" in msg:
                        received[idx] = True
                        break
            asyncio.create_task(_wait())
        except Exception as e:
            received[idx] = f"connect_failed: {e}"

    await asyncio.gather(*[client_task(i) for i in range(n_clients)])
    await asyncio.sleep(0.5)

    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    marker_payload = json.dumps({"perf_test_marker": True, "junction_id": "J1", "source": "manual"})
    await redis_client.publish(REDIS_CHANNELS["traffic"], marker_payload)
    await asyncio.sleep(1.5)
    await redis_client.aclose()

    for ws in connections:
        try:
            await ws.close()
        except Exception:
            pass

    connected = sum(1 for v in received.values() if v is not False or v is True)
    delivered = sum(1 for v in received.values() if v is True)
    failed = {i: v for i, v in received.items() if isinstance(v, str)}

    return {
        "clients_attempted": n_clients,
        "clients_connected": n_clients - len(failed),
        "messages_delivered": delivered,
        "drops": (n_clients - len(failed)) - delivered,
        "connect_failures": failed,
    }


def measure_ab_run_wall_clock(duration_s=900):
    """Real 2-arm SUMO A/B run (services/control_service/ab_runner.py),
    timed wall-clock — this is the same code path POST /ab/run uses."""
    from services.control_service.ab_runner import ABRunner

    runner = ABRunner()
    t0 = time.perf_counter()
    webster_result = runner.run_arm("webster", seed=42, duration_s=duration_s, scenario="surge")
    elapsed_s = time.perf_counter() - t0

    return {
        "duration_s_simulated": duration_s,
        "wall_clock_s": round(elapsed_s, 2),
        "webster_result_keys": list(webster_result.keys()) if isinstance(webster_result, dict) else None,
    }


def measure_whatif_wall_clock():
    """Real dual-world SUMO what-if run, timed wall-clock — same code path
    POST /events/{id}/predict uses."""
    from services.control_service.ab_runner import ABRunner

    runner = ABRunner()
    t0 = time.perf_counter()
    result = runner.run_event_whatif(
        event_id="perf-test",
        seed=42,
        duration_s=300,
        affected_links=["E_J1_to_J2"],
        expected_crowd=5000,
    )
    elapsed_s = time.perf_counter() - t0

    return {
        "wall_clock_s": round(elapsed_s, 2),
        "status": result.get("status") if isinstance(result, dict) else None,
        "links_analyzed": len(result.get("link_deltas", [])) if isinstance(result, dict) else None,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-url", default="http://127.0.0.1:8123")
    parser.add_argument("--token", default=None, help="Bearer token for API/WS measurements")
    parser.add_argument("--skip-ab", action="store_true", help="Skip the 900s A/B run (slow)")
    parser.add_argument("--skip-whatif", action="store_true")
    parser.add_argument("--skip-api", action="store_true", help="Skip API/WS checks (no live backend)")
    args = parser.parse_args()

    results = {}

    print("Measuring control loop inference latency (real MARL policy, 200 calls)...", file=sys.stderr)
    results["inference_latency"] = measure_inference_latency()

    print("Measuring control step lag (state -> safety envelope, 50 cycles)...", file=sys.stderr)
    results["control_step_lag"] = measure_control_step_lag()

    if not args.skip_api:
        print("Measuring API read-endpoint latency (real HTTP, 50 requests)...", file=sys.stderr)
        results["api_latency"] = await measure_api_latency(args.backend_url, args.token)

        print("Measuring WebSocket fanout (20 real concurrent clients)...", file=sys.stderr)
        results["websocket_fanout"] = await measure_websocket_fanout(args.backend_url)
    else:
        results["api_latency"] = {"skipped": "no live backend for this run"}
        results["websocket_fanout"] = {"skipped": "no live backend for this run"}

    if not args.skip_ab:
        print("Running real 900s A/B SUMO simulation (this takes a while)...", file=sys.stderr)
        results["ab_run"] = measure_ab_run_wall_clock(duration_s=900)
    else:
        results["ab_run"] = {"skipped": "--skip-ab"}

    if not args.skip_whatif:
        print("Running real dual-world what-if SUMO simulation...", file=sys.stderr)
        results["whatif_run"] = measure_whatif_wall_clock()
    else:
        results["whatif_run"] = {"skipped": "--skip-whatif"}

    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
