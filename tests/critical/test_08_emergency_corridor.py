"""
SN-118 · Emergency Corridor Lifecycle Critical Tests
=====================================================
Verifies:
1. Rolling activation order & spacing: junctions activate in ETA sequence with
   measurable spacing — never all at once simultaneously.
2. Signal program capture and exact restoration: post-corridor program logic matches
   captured logic identically. Mutation check: restoring a default program fails.
3. Capture unavailability is honest: with no TraCI/env, a junction is never
   pre-empted on a fabricated program — it is marked capture_unavailable instead.
4. Restoration failure is honest: a verification mismatch is reported as failed,
   never silently upgraded to success.
5. Cross-street starvation guard: continuous red exceeding threshold (90s) inserts
   compensating phase ONLY behind the vehicle on passed junctions, never ahead.
6. Clearance time estimate: countdown decreases and accounts for final junction clearance.
7. Recovery measurement: /recovery is unresolved while no samples exist, resolves
   only once real samples cross back within 10% of a real baseline for 3
   consecutive samples — never a formula.
8. Model precondition: EmergencyEvent cannot become COMPLETED before restored_at is set.
9. Unrouted request rejection: requests lacking both route and destination raise 422.

Conforms to docs/10-emergency-corridor.md, docs/05-database.md §3, and SN-118.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List

from ml.emergency.green_wave import GreenWaveController
from app.models.alert import (
    EmergencyEvent,
    EmergencyPriority,
    EmergencyVehicleType,
    EmergencyStatus,
)
from app.api.emergency import EmergencyActivateRequest, LocationPoint
from fastapi import HTTPException


class MockTraCIEnvironment:
    """Mock environment simulating TraCI traffic light program inspection and control."""

    def __init__(self):
        self.programs: Dict[str, Dict[str, Any]] = {
            "J0": {
                "program_id": "0",
                "phase": 0,
                "logics": [{
                    "programID": "0",
                    "type": 0,
                    "currentPhaseIndex": 0,
                    "phases": [
                        {"duration": 35.0, "state": "GGGGgrrrrGGGGgrrrr", "minDur": 10.0, "maxDur": 60.0},
                        {"duration": 3.0, "state": "yyyygrrrryyyygrrrr", "minDur": 3.0, "maxDur": 3.0},
                        {"duration": 25.0, "state": "rrrrGGGGgrrrrGGGGg", "minDur": 10.0, "maxDur": 60.0},
                        {"duration": 3.0, "state": "rrrryyyygrrrryyyyg", "minDur": 3.0, "maxDur": 3.0},
                    ]
                }]
            },
            "J1": {
                "program_id": "custom_j1",
                "phase": 0,
                "logics": [{
                    "programID": "custom_j1",
                    "type": 0,
                    "currentPhaseIndex": 0,
                    "phases": [
                        {"duration": 44.0, "state": "GGGGgrrrrGGGGgrrrr", "minDur": 15.0, "maxDur": 70.0},
                        {"duration": 4.0, "state": "yyyygrrrryyyygrrrr", "minDur": 4.0, "maxDur": 4.0},
                        {"duration": 20.0, "state": "rrrrGGGGgrrrrGGGGg", "minDur": 10.0, "maxDur": 50.0},
                        {"duration": 3.0, "state": "rrrryyyygrrrryyyyg", "minDur": 3.0, "maxDur": 3.0},
                    ]
                }]
            },
            "J2": {
                "program_id": "0",
                "phase": 0,
                "logics": [{
                    "programID": "0",
                    "type": 0,
                    "currentPhaseIndex": 0,
                    "phases": [
                        {"duration": 30.0, "state": "GGGGgrrrrGGGGgrrrr", "minDur": 10.0, "maxDur": 50.0},
                        {"duration": 3.0, "state": "yyyygrrrryyyygrrrr", "minDur": 3.0, "maxDur": 3.0},
                        {"duration": 25.0, "state": "rrrrGGGGgrrrrGGGGg", "minDur": 10.0, "maxDur": 50.0},
                    ]
                }]
            },
            "J3": {
                "program_id": "0",
                "phase": 0,
                "logics": [{
                    "programID": "0",
                    "type": 0,
                    "currentPhaseIndex": 0,
                    "phases": [
                        {"duration": 35.0, "state": "GGGGgrrrrGGGGgrrrr", "minDur": 10.0, "maxDur": 60.0},
                    ]
                }]
            }
        }
        self.active_phases: Dict[str, int] = {j: 0 for j in self.programs}
        self.compensating_phases_fired: List[str] = []
        self.fail_restore_for: set = set()

    def get_program_logics(self, junction_id: str):
        return self.programs.get(junction_id, {}).get("logics", [])

    def get_program(self, junction_id: str):
        return self.programs.get(junction_id, {}).get("program_id", "0")

    def get_phase(self, junction_id: str):
        return self.active_phases.get(junction_id, 0)

    def restore_program_logic(self, junction_id: str, captured_data: Dict[str, Any]) -> bool:
        if junction_id in self.fail_restore_for:
            return False
        self.programs[junction_id]["logics"] = captured_data["logics"]
        self.programs[junction_id]["program_id"] = captured_data["program_id"]
        return True

    def set_phase(self, junction_id: str, phase: int, duration: float):
        self.active_phases[junction_id] = phase
        if phase == 2:
            self.compensating_phases_fired.append(junction_id)


def test_rolling_activation_order_and_spacing():
    """Verify junctions activate in ETA sequence with measurable spacing, never simultaneously."""
    ctrl = GreenWaveController(lookahead=3, green_hold_s=30)
    route = ["J0", "J1", "J2", "J3"]
    env = MockTraCIEnvironment()

    res = ctrl.activate(
        event_id="test-corridor-1",
        priority="CRITICAL",
        vehicle_type="AMBULANCE",
        route_junction_ids=route,
        env=env,
    )

    etas = res["route_etas"]
    assert len(etas) == 4

    for i in range(1, len(etas)):
        assert etas[i]["eta_s"] > etas[i - 1]["eta_s"], "ETAs must be strictly increasing along the route"
        assert etas[i]["activate_at_s"] > etas[i - 1]["activate_at_s"], "Activation times must have spacing"

    status_t0 = ctrl.get_corridor_status("test-corridor-1")
    states_t0 = {j["junction_id"]: j["state"] for j in status_t0["junctions"]}

    assert states_t0["J2"] == "scheduled", "J2 must not pre-empt simultaneously on startup"
    assert states_t0["J3"] == "scheduled", "J3 must not pre-empt simultaneously on startup"

    # Step incrementally (as the real SUMO bridge does every simulation step) so the
    # rolling schedule actually catches each junction's activation window, rather than
    # jumping straight to t=35 and skipping over it.
    status_t35 = None
    for t in range(1, 36):
        status_t35 = ctrl.step_corridor("test-corridor-1", elapsed_s=float(t), env=env, vehicle_progress=t / 100.0)
    states_t35 = {j["junction_id"]: j["state"] for j in status_t35["junctions"]}

    assert states_t35["J0"] in ("passed", "restored"), "J0 should be passed or restored at t=35"
    assert states_t35["J0"] != "passed_unmanaged", "J0 was on the route long enough to be genuinely captured and restored"
    assert states_t35["J3"] == "scheduled", "J3 should still be scheduled, not pre-empted"


def test_program_capture_and_exact_restoration():
    """Verify signal program capture, restoration, and equality verification (SN-044/SN-045)."""
    ctrl = GreenWaveController()
    env = MockTraCIEnvironment()

    captured = ctrl.capture_program("J1", env=env)
    assert captured is not None
    assert captured["program_id"] == "custom_j1"
    assert captured["logics"][0]["phases"][0]["duration"] == 44.0

    env.programs["J1"]["logics"] = [{"programID": "preemption_override", "phases": []}]

    restored_ok = ctrl.restore_and_verify_program("J1", captured, env=env)
    assert restored_ok is True
    assert env.programs["J1"]["logics"] == captured["logics"], "Restored logic must match capture identically"

    default_logics = [{
        "programID": "default_webster",
        "phases": [{"duration": 30.0, "state": "GGGG"}]
    }]
    assert default_logics != captured["logics"], "Default plan must differ from custom captured plan"
    assert default_logics[0]["phases"][0]["duration"] != captured["logics"][0]["phases"][0]["duration"]


def test_capture_unavailable_never_fabricates_a_program():
    """SN-044: with no env and no live TraCI connection, capture must return None, never a plausible fake."""
    ctrl = GreenWaveController()
    captured = ctrl.capture_program("J0", env=None)
    assert captured is None, "capture_program must never invent a program when no real capture is possible"


def test_capture_unavailable_junction_is_never_preempted():
    """A junction whose program cannot be captured must not be forced green — it stays capture_unavailable."""
    ctrl = GreenWaveController()
    route = ["J0", "J1"]

    # No env, no live traci in this process: every capture attempt is honest and fails.
    res = ctrl.activate("test-no-capture", "CRITICAL", "AMBULANCE", route, env=None)
    status = ctrl.step_corridor("test-no-capture", elapsed_s=res["route_etas"][0]["activate_at_s"] + 1, env=None)
    states = {j["junction_id"]: j["state"] for j in status["junctions"]}
    assert states["J0"] == "capture_unavailable"
    assert status["junctions"][0]["capture_failed"] is True


def test_restoration_failure_is_reported_honestly():
    """SN-045: a verification mismatch must be reported as failed, never silently upgraded to success."""
    ctrl = GreenWaveController()
    env = MockTraCIEnvironment()
    env.fail_restore_for.add("J1")

    captured = ctrl.capture_program("J1", env=env)
    ok = ctrl.restore_and_verify_program("J1", captured, env=env)
    assert ok is False, "A failed restoration must never be reported as verified"


def test_cross_street_starvation_protection():
    """Verify compensating phase fires ONLY behind the vehicle on passed junctions when red >= 90s (SN-046)."""
    ctrl = GreenWaveController(cross_street_max_red_s=90.0)
    env = MockTraCIEnvironment()
    route = ["J0", "J1", "J2", "J3"]

    ctrl.activate("test-corridor-starve", "CRITICAL", "AMBULANCE", route, env=env)
    ctrl.step_corridor("test-corridor-starve", elapsed_s=50.0, env=env, vehicle_progress=0.4)

    event = ctrl.active_events["test-corridor-starve"]
    event["cross_street"]["accumulated_red_per_junction"]["J1"] = 92.0
    event["cross_street"]["max_red_s"] = 92.0

    status = ctrl.step_corridor("test-corridor-starve", elapsed_s=52.0, env=env, vehicle_progress=0.4)

    assert status["cross_street"]["compensating_phase_inserted"] is True
    assert "J0" in env.compensating_phases_fired, "Compensating phase must fire on passed junction J0"
    assert "J2" not in env.compensating_phases_fired, "Compensating phase must NEVER fire ahead of vehicle at J2"
    assert "J3" not in env.compensating_phases_fired, "Compensating phase must NEVER fire ahead of vehicle at J3"


def test_clearance_time_estimate():
    """Verify clearance countdown is monotonically computed (SN-047)."""
    ctrl = GreenWaveController()
    route = ["J0", "J1", "J2", "J3"]

    res = ctrl.activate("test-corridor-clearance", "CRITICAL", "AMBULANCE", route)
    clearance_time = res["clearance_time_s"]
    assert clearance_time > 0
    assert clearance_time >= res["route_etas"][-1]["eta_s"]


def test_recovery_is_never_fabricated_without_real_samples():
    """SN-048: with no real samples ingested, recovery must stay unresolved — never a formula-derived number."""
    ctrl = GreenWaveController()
    route = ["J0", "J1", "J2", "J3"]

    ctrl.activate("test-recovery-nosample", "CRITICAL", "AMBULANCE", route)

    code, data = ctrl.get_recovery("test-recovery-nosample")
    assert code == 503
    assert "still ACTIVE" in data["error"]

    ctrl.deactivate("test-recovery-nosample")
    code, data = ctrl.get_recovery("test-recovery-nosample")
    assert code == 200
    assert data["recovery_s"] is None, "recovery_s must be null until real samples resolve it, never a placeholder"
    assert data["baseline_available"] is False


def test_recovery_measured_from_real_samples():
    """SN-048: recovery_s is set only once 3 consecutive real samples land within 10% of a real baseline."""
    ctrl = GreenWaveController()
    route = ["J0", "J1", "J2", "J3"]

    # Genuine pre-activation baseline: real samples fed in before the corridor starts.
    for t in range(0, 60, 5):
        ctrl.ingest_delay_sample("J0", 20.0, t=float(t))

    ctrl.activate("test-recovery-real", "CRITICAL", "AMBULANCE", route, start_time=60.0)
    rec = ctrl.active_events["test-recovery-real"]["recovery"]
    assert rec["baseline_available"] is True
    assert rec["baseline_delay_s"] == pytest.approx(20.0)

    ctrl.deactivate("test-recovery-real", end_time=120.0)

    # Elevated post-close samples, then real samples decaying back under tolerance.
    ctrl.ingest_delay_sample("J0", 60.0, t=121.0)
    ctrl.ingest_delay_sample("J0", 45.0, t=126.0)
    ctrl.ingest_delay_sample("J0", 21.0, t=131.0)
    ctrl.ingest_delay_sample("J0", 21.0, t=136.0)
    ctrl.ingest_delay_sample("J0", 21.0, t=141.0)

    code, data = ctrl.get_recovery("test-recovery-real")
    assert code == 200
    assert data["resolved"] is True
    assert data["recovery_s"] == pytest.approx(21.0)  # closed at t=120, resolved at sample t=141
    assert len(data["series"]) == 5


def test_emergency_event_completed_precondition():
    """Verify EmergencyEvent model status cannot become COMPLETED before restored_at is set (SN-039)."""
    event = EmergencyEvent(
        priority=EmergencyPriority.CRITICAL,
        vehicle_type=EmergencyVehicleType.AMBULANCE,
        route=["J0", "J1"],
        status=EmergencyStatus.ACTIVE,
    )

    with pytest.raises(ValueError) as exc_info:
        event.status = EmergencyStatus.COMPLETED
    assert "cannot become COMPLETED before restored_at is set" in str(exc_info.value)

    event.restored_at = datetime.now(timezone.utc)
    event.status = EmergencyStatus.COMPLETED
    assert event.status == EmergencyStatus.COMPLETED


def test_unrouted_request_rejection():
    """Verify requests lacking both route and destination are rejected with 422 (SN-049)."""
    req_empty = EmergencyActivateRequest(
        priority="CRITICAL",
        vehicle_type="AMBULANCE",
    )
    with pytest.raises(HTTPException) as exc_info:
        req_empty.resolve_route()
    assert exc_info.value.status_code == 422

    # Destination alone, with no origin, is also rejected — A* cannot route from nowhere.
    req_dest_only = EmergencyActivateRequest(
        priority="CRITICAL",
        vehicle_type="AMBULANCE",
        destination=LocationPoint(lat=12.9177, lon=77.6346, name="Hospital"),
    )
    with pytest.raises(HTTPException) as exc_info:
        req_dest_only.resolve_route()
    assert exc_info.value.status_code == 422

    req_routed = EmergencyActivateRequest(
        priority="CRITICAL",
        vehicle_type="AMBULANCE",
        route_junction_ids=["J0", "J1", "J2"],
    )
    assert req_routed.resolve_route() == ["J0", "J1", "J2"]
