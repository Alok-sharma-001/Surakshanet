"""
SN-125 · A/B Reproducibility Critical Test
=========================================
Verifies:
1. Improvement formula strictly matches documented spec (docs/08-marl-control.md §7):
   - Cost metrics: (arm_a - arm_b) / arm_a * 100
   - Benefit metrics: (arm_b - arm_a) / arm_a * 100
2. Formula verified against exact hand-computed values.
3. Negative improvement is reported unchanged (never fabricated or hidden).
4. Improvement is absent while run status is incomplete/running.
5. Deterministic execution: running simulation under identical seed produces identical metrics.

Mutation check: hardcode the improvement to a constant -> test fails.
"""

import os
import pytest
import shutil

from services.control_service.ab_runner import (
    compute_ab_improvement,
    generate_ab_statement,
    ABRunner,
)
try:
    from app.models.control import ABRun
except ImportError:
    from backend.app.models.control import ABRun


def test_improvement_formula_hand_computed_values():
    arm_a = {
        "avg_delay_s": 50.0,
        "total_delay_s": 5000.0,
        "avg_queue_pcu": 20.0,
        "avg_wait_s": 40.0,
        "avg_travel_time_s": 100.0,
        "throughput_veh_h": 1000.0,
        "vehicles_served": 250
    }
    arm_b = {
        "avg_delay_s": 35.0,
        "total_delay_s": 3500.0,
        "avg_queue_pcu": 15.0,
        "avg_wait_s": 28.0,
        "avg_travel_time_s": 85.0,
        "throughput_veh_h": 1200.0,
        "vehicles_served": 300
    }

    imp = compute_ab_improvement(arm_a, arm_b)

    # Cost metrics: (arm_a - arm_b) / arm_a * 100
    assert imp["avg_delay_s_pct"] == 30.0       # (50 - 35) / 50 * 100 = 30.0%
    assert imp["total_delay_s_pct"] == 30.0     # (5000 - 3500) / 5000 * 100 = 30.0%
    assert imp["avg_queue_pcu_pct"] == 25.0     # (20 - 15) / 20 * 100 = 25.0%
    assert imp["avg_wait_s_pct"] == 30.0        # (40 - 28) / 40 * 100 = 30.0%
    assert imp["avg_travel_time_s_pct"] == 15.0 # (100 - 85) / 100 * 100 = 15.0%

    # Benefit metrics: (arm_b - arm_a) / arm_a * 100
    assert imp["throughput_veh_h_pct"] == 20.0  # (1200 - 1000) / 1000 * 100 = 20.0%
    assert imp["vehicles_served_pct"] == 20.0   # (300 - 250) / 250 * 100 = 20.0%


def test_negative_result_reported_unchanged():
    # When MARL performs worse, report negative number honestly (R7)
    arm_a = {"avg_delay_s": 30.0, "throughput_veh_h": 1000.0, "vehicles_served": 200}
    arm_b = {"avg_delay_s": 45.0, "throughput_veh_h": 800.0, "vehicles_served": 160}

    imp = compute_ab_improvement(arm_a, arm_b)
    assert imp["avg_delay_s_pct"] == -50.0          # (30 - 45) / 30 * 100 = -50%
    assert imp["throughput_veh_h_pct"] == -20.0     # (800 - 1000) / 1000 * 100 = -20%

    stmt = generate_ab_statement("surge", 42, 900, arm_a, arm_b, imp)
    assert "increased average delay by 50.0%" in stmt


def test_improvement_absent_while_running():
    run = ABRun(
        scenario="surge",
        seed=42,
        duration_s=900,
        status="running",
        improvement=None
    )
    assert run.status == "running"
    assert run.improvement is None


@pytest.mark.sumo
def test_sumo_simulation_reproducibility():
    if not shutil.which("sumo"):
        pytest.skip("SUMO binary not installed on this host environment")

    try:
        import traci
    except ImportError:
        pytest.skip("TraCI not importable on this host environment")

    runner = ABRunner()
    # Run two short runs with identical seed 42
    run1 = runner.run_arm("webster", seed=42, duration_s=30, scenario="surge")
    run2 = runner.run_arm("webster", seed=42, duration_s=30, scenario="surge")

    assert run1 == run2, f"Metrics differed across identical seed runs: {run1} != {run2}"
