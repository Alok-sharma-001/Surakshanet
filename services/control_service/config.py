"""
SurakshaNet Control Service Configuration
=========================================
Defines operational parameters, safety thresholds, and feature normalisation constants.
Conforms to docs/08-marl-control.md §2, §4, §5.
"""

import os
from dataclasses import dataclass
from shared.constants import SIGNAL_CONSTRAINTS

# Timing and control loop
CONTROL_STEP_S = 5.0                        # Decision loop step in seconds
MIN_GREEN_S = SIGNAL_CONSTRAINTS.get("min_green", 10.0)      # Hard minimum green time (s)
MAX_GREEN_S = SIGNAL_CONSTRAINTS.get("max_green", 60.0)      # Hard maximum green time (s)
AMBER_S = SIGNAL_CONSTRAINTS.get("yellow_duration", 3.0)     # Mandatory amber transition (s)
ALL_RED_S = SIGNAL_CONSTRAINTS.get("all_red", 2.0)           # Mandatory all-red clearance (s)
MAX_CYCLES_WITHOUT_PED = 2                  # Pedestrian service guarantee limit

# State normalisation constants (Fixed order matching DQN training)
NORM_QUEUE_MAX = 50.0                       # PCU: queue_length / 50.0, clip [0, 1]
NORM_SPEED_MAX = 60.0                       # km/h: mean_speed / 60.0, clip [0, 1]
NORM_WAIT_MAX = 300.0                       # s: accumulated_wait / 300.0, clip [0, 1]
N_PHASES = 4                                # phase_index / (N_PHASES - 1)

# Reward computation
LAMBDA_WAIT = 0.01                          # Penalty weight for accumulated wait time

# Fault tolerance
MAX_TELEMETRY_GAP_S = 2 * CONTROL_STEP_S    # 10.0s gap threshold before Webster fallback
MODE_POLL_INTERVAL_S = 5.0                  # DB mode polling interval

# Policy weights and junction
DEFAULT_JUNCTION_ID = os.environ.get("JUNCTION_ID", "J1")
WEIGHTS_PATH = os.environ.get(
    "MARL_WEIGHTS_PATH",
    "ml/marl/weights/marl_policy_downtown.pth"
)


@dataclass
class ControlConfig:
    junction_id: str = DEFAULT_JUNCTION_ID
    control_step_s: float = CONTROL_STEP_S
    min_green_s: float = MIN_GREEN_S
    max_green_s: float = MAX_GREEN_S
    amber_s: float = AMBER_S
    all_red_s: float = ALL_RED_S
    max_cycles_without_ped: int = MAX_CYCLES_WITHOUT_PED
    norm_queue_max: float = NORM_QUEUE_MAX
    norm_speed_max: float = NORM_SPEED_MAX
    norm_wait_max: float = NORM_WAIT_MAX
    n_phases: int = N_PHASES
    lambda_wait: float = LAMBDA_WAIT
    max_telemetry_gap_s: float = MAX_TELEMETRY_GAP_S
    weights_path: str = WEIGHTS_PATH
