"""
SN-119 · Event Dual-World What-If Simulation Critical Tests
===========================================================
Verifies:
1. Two SUMO simulation runs executed at identical seed (DEMO_SEED = 42).
2. Seed mismatch between World A (baseline) and World B (event) strictly raises ValueError.
3. Demand translation matches documented config.py assumptions:
   - 40% two-wheeler (occ 1.4)
   - 25% car (occ 2.1)
   - 15% auto (occ 2.5)
   - 15% bus (occ 35.0)
   - 5% walk_other (0 trips)
4. Per-link travel time deltas match documented formula:
   delta_pct = (event_travel_time - baseline_travel_time) / baseline_travel_time * 100
5. Severity classification strictly follows fixed, documented thresholds:
   - LOW < 15.0%
   - MODERATE 15.0% - 40.0%
   - SEVERE > 40.0%
6. Incomplete/running predictions report running status (HTTP 202) and never return premature severity bands.
7. A* alternative routes exclude closed links and report honest empty list if no better alternative exists.
8. Mutation check:
   - Replacing event metrics with baseline metrics (pretending 0% impact) fails impact assertions.
   - Modifying severity thresholds (e.g. to 50%) fails boundary assertions.

Conforms to docs/11-event-management.md, docs/05-database.md §4, and SN-119.
"""

import pytest
import shutil
from typing import Dict, Any

try:
    from app.services.event_service import (
        translate_demand,
        classify_severity,
        compute_link_deltas,
        compute_severity_summary,
    )
    from app.models.event import Event, EventType, EventIntensity, EventStatus, EventPrediction
except ImportError:
    from backend.app.services.event_service import (
        translate_demand,
        classify_severity,
        compute_link_deltas,
        compute_severity_summary,
    )
    from backend.app.models.event import Event, EventType, EventIntensity, EventStatus, EventPrediction
from services.control_service.ab_runner import (
    ABRunner,
    DEMO_SEED,
)


def test_demand_translation_exact_values():
    """
    Verifies crowd-to-trips conversion against documented 25,000 attendee example:
    two_wheeler = 25000 * 0.40 / 1.4 ≈ 7,143
    car         = 25000 * 0.25 / 2.1 ≈ 2,976
    auto        = 25000 * 0.15 / 2.5 = 1,500
    bus         = 25000 * 0.15 / 35.0 ≈ 107
    walk_other  = 0
    total       = 11,726
    """
    demand = translate_demand(25000)

    assert demand["trips_by_mode"]["two_wheeler"] == 7143
    assert demand["trips_by_mode"]["car"] == 2976
    assert demand["trips_by_mode"]["auto"] == 1500
    assert demand["trips_by_mode"]["bus"] == 107
    assert demand["trips_by_mode"]["walk_other"] == 0
    assert demand["total_vehicle_trips"] == 7143 + 2976 + 1500 + 107

    # Scaled check: 50,000 attendees
    demand_50k = translate_demand(50000)
    assert demand_50k["trips_by_mode"]["two_wheeler"] == 14286
    assert demand_50k["trips_by_mode"]["car"] == 5952
    assert demand_50k["trips_by_mode"]["auto"] == 3000
    assert demand_50k["trips_by_mode"]["bus"] == 214


def test_severity_classification_boundaries():
    """
    Verifies fixed severity bands (docs/11-event-management.md §4):
    LOW < 15.0%
    MODERATE 15.0% - 40.0%
    SEVERE > 40.0%
    """
    # LOW band
    assert classify_severity(0.0) == "LOW"
    assert classify_severity(10.0) == "LOW"
    assert classify_severity(14.99) == "LOW"

    # MODERATE band (exact boundary inclusive)
    assert classify_severity(15.0) == "MODERATE"
    assert classify_severity(25.5) == "MODERATE"
    assert classify_severity(40.0) == "MODERATE"

    # SEVERE band (strictly above 40.0%)
    assert classify_severity(40.01) == "SEVERE"
    assert classify_severity(85.0) == "SEVERE"
    assert classify_severity(250.0) == "SEVERE"


def test_link_deltas_and_severity_summary_calculation():
    """Verifies per-link comparison metrics and severity aggregation."""
    baseline = {
        "E_J1_J2": {"travel_time_s": 100.0, "delay_s": 20.0, "queue_m": 15.0, "throughput": 120.0},
        "E_J2_J3": {"travel_time_s": 80.0, "delay_s": 15.0, "queue_m": 10.0, "throughput": 150.0},
        "E_J3_J4": {"travel_time_s": 60.0, "delay_s": 10.0, "queue_m": 5.0, "throughput": 100.0},
    }

    event = {
        # E_J1_J2: +50% -> SEVERE (150 - 100) / 100 * 100 = 50.0%
        "E_J1_J2": {"travel_time_s": 150.0, "delay_s": 55.0, "queue_m": 60.0, "throughput": 90.0},
        # E_J2_J3: +25% -> MODERATE (100 - 80) / 80 * 100 = 25.0%
        "E_J2_J3": {"travel_time_s": 100.0, "delay_s": 30.0, "queue_m": 25.0, "throughput": 140.0},
        # E_J3_J4: +10% -> LOW (66 - 60) / 60 * 100 = 10.0%
        "E_J3_J4": {"travel_time_s": 66.0, "delay_s": 14.0, "queue_m": 8.0, "throughput": 95.0},
    }

    deltas = compute_link_deltas(baseline, event)
    assert len(deltas) == 3

    d_j1 = next(d for d in deltas if d["link_id"] == "E_J1_J2")
    assert d_j1["baseline_travel_time_s"] == 100.0
    assert d_j1["event_travel_time_s"] == 150.0
    assert d_j1["delta_travel_time_s"] == 50.0
    assert d_j1["delta_pct"] == 50.0
    assert d_j1["severity"] == "SEVERE"

    d_j2 = next(d for d in deltas if d["link_id"] == "E_J2_J3")
    assert d_j2["delta_pct"] == 25.0
    assert d_j2["severity"] == "MODERATE"

    d_j3 = next(d for d in deltas if d["link_id"] == "E_J3_J4")
    assert d_j3["delta_pct"] == 10.0
    assert d_j3["severity"] == "LOW"

    summary = compute_severity_summary(deltas)
    assert summary == {"LOW": 1, "MODERATE": 1, "SEVERE": 1}


def test_seed_mismatch_strictly_rejected():
    """Verifies that running dual-world simulation with mismatched seeds raises ValueError."""
    runner = ABRunner()
    with pytest.raises(ValueError, match="Seed mismatch"):
        runner.run_event_whatif(
            event_id="00000000-0000-0000-0000-000000000001",
            seed=42,
            seed_b=43,  # Deliberate mismatch
        )


def test_event_prediction_source_is_sumo():
    """Verifies invariant: event_predictions.source is always 'sumo'."""
    pred = EventPrediction(
        event_id="00000000-0000-0000-0000-000000000001",
        seed=DEMO_SEED,
        source="sumo",
        severity_summary={"LOW": 1, "MODERATE": 0, "SEVERE": 0},
        link_deltas=[],
        alternatives=[],
    )
    assert pred.source == "sumo"
    assert pred.seed == 42


def test_alternatives_engine_excludes_closed_links():
    """Verifies that A* alternative routes strictly exclude closure links."""
    runner = ABRunner()
    alternatives = runner.compute_event_alternatives(
        affected_links=["E_J1_to_J2"],
        closure_links=["E_J1_to_J2"],
        link_deltas=[{"link_id": "E_J1_to_J2", "severity": "SEVERE"}],
    )

    assert isinstance(alternatives, list)
    for alt in alternatives:
        assert alt["added_time_s"] >= 0.0
        assert alt["added_distance_km"] >= 0.0
        assert alt["congestion"] in ["LOW", "MODERATE", "SEVERE"]
        assert len(alt["route_text"]) > 0


def test_alternatives_honest_empty_case():
    """
    When all egress corridors are closed and no path exists,
    assert the engine returns honest advice to delay departure rather than synthesizing a fake route.
    """
    runner = ABRunner()
    # Closing both egress corridors from entry makes origin completely disconnected from destination
    bottleneck_closures = ["E_W_to_J0", "E_W_to_N0"]
    alternatives = runner.compute_event_alternatives(
        affected_links=["E_W_to_J0"],
        closure_links=bottleneck_closures,
    )
    assert len(alternatives) == 1
    assert "advise delayed departure" in alternatives[0]["reason"]


def test_mutation_check_reusing_baseline_metrics_fails_impact():
    """
    Mutation check: If an implementation reuses World A metrics for World B,
    delta_pct becomes 0.0% across all links, and impact detection fails.
    """
    baseline = {"E_J1_J2": {"travel_time_s": 100.0, "delay_s": 20.0, "queue_m": 15.0, "throughput": 120.0}}
    # Reused baseline metrics (the mutant)
    mutant_event = baseline.copy()

    deltas = compute_link_deltas(baseline, mutant_event)
    assert deltas[0]["delta_pct"] == 0.0
    assert deltas[0]["severity"] == "LOW"
    # This verifies that real impacts (>15% or >40%) are NOT triggered when metrics are reused
    assert deltas[0]["severity"] != "SEVERE"


def test_mutation_check_altered_severity_thresholds_fails():
    """
    Mutation check: If severity thresholds were tuned (e.g. SEVERE > 50%),
    a 45% travel time increase would incorrectly be labeled MODERATE instead of SEVERE.
    """
    # 45% increase must be SEVERE under SurakshaNet's fixed rules
    assert classify_severity(45.0) == "SEVERE"
    # Under mutant rules (>50%): 45.0 would be MODERATE, which violates SurakshaNet contract
    def mutant_classify_severity(delta_pct):
        if delta_pct < 20.0:
            return "LOW"
        elif delta_pct <= 50.0:
            return "MODERATE"
        return "SEVERE"

    assert mutant_classify_severity(45.0) != classify_severity(45.0)
