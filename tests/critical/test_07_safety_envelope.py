"""
SN-117 · Safety Envelope Critical Test
======================================
Verifies:
1. Minimum green clamp (10s): attempting to ADVANCE at 2s elapsed is clamped to EXTEND.
2. Maximum green clamp (60s): attempting to EXTEND at >=60s elapsed is clamped to ADVANCE.
3. Pedestrian service guarantee: fires after max_cycles_without_ped.
4. Emergency preemption override outranks policy.
5. Allowed action passes through when within constraints.

Mutation check: set min_green_s = 0 in config or safety envelope -> test_min_green_clamp fails.
"""

import pytest
from services.control_service.config import ControlConfig, MIN_GREEN_S, MAX_GREEN_S
from services.control_service.safety import (
    SafetyEnvelope,
    JunctionRuntimeState,
    ACTION_EXTEND,
    ACTION_ADVANCE,
)


def test_min_green_clamp():
    cfg = ControlConfig(min_green_s=10.0, max_green_s=60.0)
    envelope = SafetyEnvelope(cfg)

    # State with only 2.0 seconds elapsed green
    state = JunctionRuntimeState(
        junction_id="J1",
        current_phase=0,
        phase_elapsed_s=2.0,
        cycles_since_pedestrian_phase=0
    )

    # Policy wants to advance immediately
    result = envelope.evaluate(action=ACTION_ADVANCE, state=state)

    assert result.clamped is True
    assert result.action == ACTION_EXTEND
    assert result.clamp_reason == "min_green_not_elapsed"
    assert result.action_source == "safety_clamp"
    assert result.applied_phase == 0


def test_max_green_clamp():
    cfg = ControlConfig(min_green_s=10.0, max_green_s=60.0)
    envelope = SafetyEnvelope(cfg)

    # State with 60.0 seconds elapsed green
    state = JunctionRuntimeState(
        junction_id="J1",
        current_phase=0,
        phase_elapsed_s=60.0,
        cycles_since_pedestrian_phase=0
    )

    # Policy wants to keep extending
    result = envelope.evaluate(action=ACTION_EXTEND, state=state)

    assert result.clamped is True
    assert result.action == ACTION_ADVANCE
    assert result.clamp_reason == "max_green_exceeded"
    assert result.action_source == "safety_clamp"
    assert result.applied_phase == 1


def test_pedestrian_service_guarantee():
    cfg = ControlConfig(max_cycles_without_ped=2)
    envelope = SafetyEnvelope(cfg)

    # 2 cycles without pedestrian phase
    state = JunctionRuntimeState(
        junction_id="J1",
        current_phase=0,
        phase_elapsed_s=25.0,
        cycles_since_pedestrian_phase=2
    )

    # Policy wants to extend
    result = envelope.evaluate(action=ACTION_EXTEND, state=state)

    assert result.clamped is True
    assert result.action == ACTION_ADVANCE
    assert result.clamp_reason == "pedestrian_service_due"
    assert result.action_source == "safety_clamp"


def test_emergency_preemption_override():
    envelope = SafetyEnvelope()

    state = JunctionRuntimeState(
        junction_id="J1",
        current_phase=2,
        phase_elapsed_s=5.0,
        emergency_preemption_active=True
    )

    result = envelope.evaluate(action=ACTION_EXTEND, state=state)

    assert result.clamped is True
    assert result.clamp_reason == "emergency_corridor"
    assert result.action_source == "emergency"
    assert result.applied_phase == 0


def test_unconstrained_action_allowed():
    cfg = ControlConfig(min_green_s=10.0, max_green_s=60.0)
    envelope = SafetyEnvelope(cfg)

    # State with 25s elapsed (between 10s and 60s)
    state = JunctionRuntimeState(
        junction_id="J1",
        current_phase=0,
        phase_elapsed_s=25.0,
        cycles_since_pedestrian_phase=0
    )

    # Policy decides to advance
    result = envelope.evaluate(action=ACTION_ADVANCE, state=state)

    assert result.clamped is False
    assert result.clamp_reason is None
    assert result.action == ACTION_ADVANCE
    assert result.action_source == "policy"
    assert result.applied_phase == 1
