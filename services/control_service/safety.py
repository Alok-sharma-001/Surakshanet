"""
SurakshaNet Control Service Safety Envelope (SN-032)
===================================================
Mandatory safety constraints applied outside the policy to every action.
The policy has NO path around this envelope.
Conforms to docs/08-marl-control.md §5 and §6.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

from services.control_service.config import ControlConfig, MIN_GREEN_S, MAX_GREEN_S

# Action definitions
ACTION_EXTEND = 0
ACTION_ADVANCE = 1


@dataclass
class JunctionRuntimeState:
    junction_id: str
    current_phase: int
    phase_elapsed_s: float
    cycles_since_pedestrian_phase: int = 0
    emergency_preemption_active: bool = False
    in_amber_transition: bool = False
    amber_elapsed_s: float = 0.0


@dataclass
class SafetyResult:
    action: int                        # 0 = EXTEND, 1 = ADVANCE
    clamped: bool
    clamp_reason: Optional[str]
    action_source: str                 # 'policy' | 'safety_clamp' | 'emergency' | 'operator'
    applied_phase: int
    applied_duration_s: float


class SafetyEnvelope:
    """
    Evaluates actions against hard physical constraints:
    1. Minimum green (10s): cannot advance before min_green_s has elapsed.
    2. Maximum green (60s): cannot extend once max_green_s is reached.
    3. Mandatory amber/all-red transition sequencing.
    4. Pedestrian service guarantee (cannot exceed max_cycles_without_ped).
    5. Emergency vehicle pre-emption override.
    """

    def __init__(self, cfg: Optional[ControlConfig] = None):
        self.cfg = cfg or ControlConfig()

    def evaluate(
        self,
        action: int,
        state: JunctionRuntimeState,
        controller_name: str = "marl"
    ) -> SafetyResult:
        cfg = self.cfg

        # 1. Emergency pre-emption outranks the policy entirely
        if state.emergency_preemption_active:
            return SafetyResult(
                action=ACTION_ADVANCE,
                clamped=True,
                clamp_reason="emergency_corridor",
                action_source="emergency",
                applied_phase=0,  # Green wave corridor axis
                applied_duration_s=9999.0
            )

        # 2. Pedestrian service guarantee
        if state.cycles_since_pedestrian_phase >= cfg.max_cycles_without_ped:
            return SafetyResult(
                action=ACTION_ADVANCE,
                clamped=True,
                clamp_reason="pedestrian_service_due",
                action_source="safety_clamp",
                applied_phase=(state.current_phase + 1) % cfg.n_phases,
                applied_duration_s=cfg.amber_s
            )

        # 3. Minimum green clamp
        if action == ACTION_ADVANCE and state.phase_elapsed_s < cfg.min_green_s:
            return SafetyResult(
                action=ACTION_EXTEND,
                clamped=True,
                clamp_reason="min_green_not_elapsed",
                action_source="safety_clamp",
                applied_phase=state.current_phase,
                applied_duration_s=cfg.control_step_s
            )

        # 4. Maximum green clamp
        if action == ACTION_EXTEND and state.phase_elapsed_s >= cfg.max_green_s:
            return SafetyResult(
                action=ACTION_ADVANCE,
                clamped=True,
                clamp_reason="max_green_exceeded",
                action_source="safety_clamp",
                applied_phase=(state.current_phase + 1) % cfg.n_phases,
                applied_duration_s=cfg.amber_s
            )

        # 5. Policy action allowed unchanged
        if action == ACTION_ADVANCE:
            next_phase = (state.current_phase + 1) % cfg.n_phases
            duration = cfg.amber_s
        else:
            next_phase = state.current_phase
            duration = cfg.control_step_s

        return SafetyResult(
            action=action,
            clamped=False,
            clamp_reason=None,
            action_source="policy",
            applied_phase=next_phase,
            applied_duration_s=duration
        )
