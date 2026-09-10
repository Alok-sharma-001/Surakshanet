"""
SurakshaNet Control Service State Builder (SN-034)
=================================================
Transforms canonical JunctionTelemetry into the exact 8-dimensional state vector
expected by the trained MARL policy network.
Conforms to docs/08-marl-control.md §2.

Vector Features (ordered):
0: queue_length       (PCU, max over approaches / 50.0, clip [0, 1])
1: mean_speed          (km/h, PCU-weighted mean / 60.0, clip [0, 1])
2: occupancy           (ratio, max over approaches, [0, 1])
3: accumulated_wait    (s, max over approaches / 300.0, clip [0, 1])
4: phase_index         (int, current_phase / (n_phases - 1))
5: elapsed_green       (s, phase_elapsed_s / max_green_s, clip [0, 1])
6: tod_sin             (sin(2π · seconds_of_day / 86400) IST)
7: tod_cos             (cos(2π · seconds_of_day / 86400) IST)
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import numpy as np

from shared.telemetry import JunctionTelemetry
from services.control_service.config import ControlConfig, CONTROL_STEP_S

IST_OFFSET = timedelta(hours=5, minutes=30)
REQUIRED_APPROACHES = frozenset({"N", "E", "S", "W"})


class StateBuildResult:
    """Encapsulates the constructed state vector, raw inputs, and validity status."""
    def __init__(
        self,
        vector: List[float],
        raw_values: Dict[str, Any],
        norm_constants: Dict[str, Any],
        is_valid: bool = True,
        fallback_reason: Optional[str] = None
    ):
        self.vector = vector
        self.raw_values = raw_values
        self.norm_constants = norm_constants
        self.is_valid = is_valid
        self.fallback_reason = fallback_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vector": [round(float(v), 6) for v in self.vector],
            "raw": self.raw_values,
            "norm_constants": self.norm_constants,
            "is_valid": self.is_valid,
            "fallback_reason": self.fallback_reason
        }

    @property
    def numpy_vector(self) -> np.ndarray:
        return np.array(self.vector, dtype=np.float32)


def build_state_vector(
    telemetry: JunctionTelemetry,
    cfg: Optional[ControlConfig] = None,
    last_telemetry_time: Optional[float] = None
) -> StateBuildResult:
    """
    Constructs an 8-dim state vector strictly matching the DQN training format.
    If approaches are incomplete or telemetry has a gap > 2 * control_step_s,
    is_valid is set to False with fallback_reason recorded.
    """
    cfg = cfg or ControlConfig()
    norm_constants = {
        "norm_queue_max": cfg.norm_queue_max,
        "norm_speed_max": cfg.norm_speed_max,
        "norm_wait_max": cfg.norm_wait_max,
        "max_green_s": cfg.max_green_s,
        "n_phases": cfg.n_phases
    }

    # 1. Missing data check
    approaches = telemetry.approaches or []
    present_dirs = {a.direction for a in approaches}
    if not REQUIRED_APPROACHES.issubset(present_dirs):
        missing = sorted(list(REQUIRED_APPROACHES - present_dirs))
        return StateBuildResult(
            vector=[0.0] * 8,
            raw_values={},
            norm_constants=norm_constants,
            is_valid=False,
            fallback_reason=f"missing_approaches: {missing}"
        )

    # 2. Telemetry gap check
    if last_telemetry_time is not None and telemetry.sim_time_s is not None:
        gap = telemetry.sim_time_s - last_telemetry_time
        if gap > cfg.max_telemetry_gap_s:
            return StateBuildResult(
                vector=[0.0] * 8,
                raw_values={},
                norm_constants=norm_constants,
                is_valid=False,
                fallback_reason=f"telemetry_gap_{gap:.1f}s_exceeded_{cfg.max_telemetry_gap_s:.1f}s"
            )

    # 3. Extract raw values
    # Feature 0: queue_length (PCU, max over approaches)
    raw_queue = max((a.pcu for a in approaches), default=0.0)
    feat_0_queue = min(1.0, max(0.0, raw_queue / cfg.norm_queue_max))

    # Feature 1: mean_speed (km/h, PCU-weighted mean)
    total_pcu = sum(a.pcu for a in approaches)
    if total_pcu > 0:
        raw_speed = sum(a.mean_speed_kmh * a.pcu for a in approaches) / total_pcu
    else:
        raw_speed = sum(a.mean_speed_kmh for a in approaches) / len(approaches)
    feat_1_speed = min(1.0, max(0.0, raw_speed / cfg.norm_speed_max))

    # Feature 2: occupancy (ratio, max over approaches)
    raw_occ = max((a.occupancy for a in approaches), default=0.0)
    feat_2_occ = min(1.0, max(0.0, raw_occ))

    # Feature 3: accumulated_wait (s, max over approaches)
    raw_wait = max((a.accumulated_wait_s for a in approaches), default=0.0)
    feat_3_wait = min(1.0, max(0.0, raw_wait / cfg.norm_wait_max))

    # Feature 4: phase_index (int, current_phase / (n_phases - 1))
    raw_phase = int(telemetry.current_phase)
    phase_divisor = max(1, cfg.n_phases - 1)
    feat_4_phase = min(1.0, max(0.0, float(raw_phase) / phase_divisor))

    # Feature 5: elapsed_green (s, phase_elapsed_s / max_green_s)
    raw_elapsed = float(telemetry.phase_elapsed_s)
    feat_5_elapsed = min(1.0, max(0.0, raw_elapsed / cfg.max_green_s))

    # Feature 6 & 7: Time-of-Day sin & cos (IST)
    try:
        ts_str = telemetry.timestamp.replace("Z", "+00:00")
        dt_utc = datetime.fromisoformat(ts_str)
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    except Exception:
        dt_utc = datetime.now(timezone.utc)

    dt_ist = dt_utc.astimezone(timezone(IST_OFFSET))
    seconds_of_day = (
        dt_ist.hour * 3600
        + dt_ist.minute * 60
        + dt_ist.second
        + dt_ist.microsecond / 1e6
    )
    tod_angle = 2.0 * math.pi * seconds_of_day / 86400.0
    feat_6_tod_sin = math.sin(tod_angle)
    feat_7_tod_cos = math.cos(tod_angle)

    vector = [
        feat_0_queue,
        feat_1_speed,
        feat_2_occ,
        feat_3_wait,
        feat_4_phase,
        feat_5_elapsed,
        feat_6_tod_sin,
        feat_7_tod_cos
    ]

    raw_values = {
        "queue_length": round(raw_queue, 2),
        "mean_speed": round(raw_speed, 2),
        "occupancy": round(raw_occ, 4),
        "accumulated_wait": round(raw_wait, 2),
        "phase_index": raw_phase,
        "elapsed_green": round(raw_elapsed, 2),
        "seconds_of_day_ist": round(seconds_of_day, 1)
    }

    return StateBuildResult(
        vector=vector,
        raw_values=raw_values,
        norm_constants=norm_constants,
        is_valid=True
    )
