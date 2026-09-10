"""
SurakshaNet Control Service Reward Computation (SN-035)
======================================================
Computes decision reward one step after an action is applied:
r_t = -(Σ queue_t - Σ queue_{t-1}) - λ · Σ wait_t
with λ = 0.01.

Stage phrasing:
"The agent is paid to shrink the queue and penalised for making anyone wait."
Conforms to docs/08-marl-control.md §4.
"""

from typing import Dict, Any, Optional
from services.control_service.config import ControlConfig, LAMBDA_WAIT


def compute_reward(
    current_total_queue: float,
    previous_total_queue: float,
    current_total_wait: float,
    lambda_wait: float = LAMBDA_WAIT
) -> float:
    """
    Computes step reward based on queue difference and accumulated wait penalty.

    Args:
        current_total_queue: Sum of queues across all approaches at step t
        previous_total_queue: Sum of queues across all approaches at step t-1
        current_total_wait: Sum of wait times across all approaches at step t
        lambda_wait: Weight factor for wait time penalty (default: 0.01)

    Returns:
        float reward value rounded to 4 decimal places
    """
    delta_queue = current_total_queue - previous_total_queue
    wait_penalty = lambda_wait * current_total_wait
    reward = -delta_queue - wait_penalty
    return round(float(reward), 4)


class RewardTracker:
    """Tracks previous step queues to calculate reward on subsequent decision step."""

    def __init__(self, lambda_wait: float = LAMBDA_WAIT):
        self.lambda_wait = lambda_wait
        self.last_queues: Dict[str, float] = {}  # junction_id -> previous total queue

    def step(
        self,
        junction_id: str,
        current_queue: float,
        current_wait: float
    ) -> Optional[float]:
        """
        Calculates reward if previous step queue is known, and updates history.
        """
        prev_queue = self.last_queues.get(junction_id)
        self.last_queues[junction_id] = current_queue

        if prev_queue is None:
            return None

        return compute_reward(
            current_total_queue=current_queue,
            previous_total_queue=prev_queue,
            current_total_wait=current_wait,
            lambda_wait=self.lambda_wait
        )
