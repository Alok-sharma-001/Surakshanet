"""
SurakshaNet Signal Controllers (SN-031)
=======================================
Implements the three core controller strategies behind a unified interface:
1. MarlController: Deep Q-Network policy with real PyTorch weights (greedy, epsilon=0.0).
2. WebsterController: Fixed-time TOD and flow-ratio Webster formula fallback.
3. ManualController: Operator manual signal commands.

Conforms to docs/08-marl-control.md §3 and §6.
"""

import hashlib
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import numpy as np

from ml.marl.webster_fallback import WebsterFallback
from services.control_service.config import ControlConfig, WEIGHTS_PATH
from services.control_service.safety import ACTION_EXTEND, ACTION_ADVANCE

logger = logging.getLogger("surakshanet.controllers")


@dataclass
class ControllerDecision:
    action: int                                 # 0 = EXTEND, 1 = ADVANCE
    q_values: Optional[List[float]]             # List of floats for MARL, None for others
    controller_name: str                        # "marl" | "webster" | "manual"
    model_version: Optional[str] = None         # SHA-256 for MARL
    metadata: Optional[Dict[str, Any]] = None


class BaseController(ABC):
    controller_name: str = "base"

    @abstractmethod
    def select_action(
        self,
        junction_id: str,
        state_vector: np.ndarray,
        current_phase: int,
        phase_elapsed_s: float,
        **kwargs
    ) -> ControllerDecision:
        """Select action 0 (EXTEND) or 1 (ADVANCE) given junction state."""
        pass


class MarlController(BaseController):
    """
    Greedy Deep Q-Network controller using the trained PyTorch model.
    Zero exploration (epsilon=0.0) for deterministic demo execution.
    """
    controller_name: str = "marl"

    def __init__(self, weights_path: str = WEIGHTS_PATH):
        self.weights_path = weights_path
        self.policy_net = None
        self.model_version: Optional[str] = None
        self.is_loaded = False
        self._load_policy()

    def _load_policy(self):
        if not os.path.exists(self.weights_path):
            logger.warning(f"MARL weights not found at {self.weights_path}. MARL mode will be refused.")
            self.is_loaded = False
            return

        # Compute SHA-256
        h = hashlib.sha256()
        with open(self.weights_path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        self.model_version = h.hexdigest()

        try:
            import torch
            from ml.marl.networks import QNetwork

            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.policy_net = QNetwork(state_dim=8, action_dim=2).to(self.device)

            checkpoint = torch.load(self.weights_path, map_location=self.device)
            if "policy_net_state_dict" in checkpoint:
                self.policy_net.load_state_dict(checkpoint["policy_net_state_dict"])
            else:
                self.policy_net.load_state_dict(checkpoint)

            self.policy_net.eval()
            self.is_loaded = True
            logger.info(f"Loaded MARL policy weights (SHA-256: {self.model_version[:12]}...)")
        except Exception as e:
            logger.error(f"Failed to load MARL weights: {e}. MARL mode unavailable.")
            self.is_loaded = False

    def select_action(
        self,
        junction_id: str,
        state_vector: np.ndarray,
        current_phase: int,
        phase_elapsed_s: float,
        **kwargs
    ) -> ControllerDecision:
        if not self.is_loaded or self.policy_net is None:
            raise RuntimeError("MARL controller weights not loaded. Refusing MARL execution.")

        import torch
        with torch.no_grad():
            s_tensor = torch.FloatTensor(state_vector).unsqueeze(0).to(self.device)
            q_out = self.policy_net(s_tensor).cpu().numpy().flatten()

        q_list = [round(float(q), 4) for q in q_out]
        action = int(np.argmax(q_out))

        return ControllerDecision(
            action=action,
            q_values=q_list,
            controller_name="marl",
            model_version=self.model_version,
            metadata={"greedy": True, "epsilon": 0.0}
        )


class WebsterController(BaseController):
    """
    Fixed-time and flow-ratio Webster fallback controller.
    Uses Webster's equation and time-of-day plans from ml/marl/webster_fallback.py.
    """
    controller_name: str = "webster"

    def __init__(self):
        self.webster = WebsterFallback()

    def select_action(
        self,
        junction_id: str,
        state_vector: np.ndarray,
        current_phase: int,
        phase_elapsed_s: float,
        demands: Optional[Dict[str, float]] = None,
        **kwargs
    ) -> ControllerDecision:
        # Determine plan based on current demands or time of day
        if demands:
            plan = self.webster.calculate_webster_optimal(demands)
        else:
            plan = self.webster.get_current_plan()

        ns_green = plan.get("ns_green", 40)
        ew_green = plan.get("ew_green", 40)

        # For corridor network: Phase 0 is EW green, Phase 2 is NS green
        if current_phase == 0:
            target_green = ew_green
        elif current_phase == 2:
            target_green = ns_green
        else:
            # In amber phases (1 or 3), advance once amber duration elapses
            target_green = 3.0

        if phase_elapsed_s >= target_green:
            action = ACTION_ADVANCE
        else:
            action = ACTION_EXTEND

        return ControllerDecision(
            action=action,
            q_values=None,
            controller_name="webster",
            model_version=None,
            metadata={"plan": plan, "target_green_s": target_green}
        )


class ManualController(BaseController):
    """
    Operator manual controller. Executes explicit commands received from dashboard.
    """
    controller_name: str = "manual"

    def __init__(self):
        self.manual_commands: Dict[str, int] = {}  # junction_id -> requested_action

    def set_manual_command(self, junction_id: str, action: int):
        self.manual_commands[junction_id] = action

    def select_action(
        self,
        junction_id: str,
        state_vector: np.ndarray,
        current_phase: int,
        phase_elapsed_s: float,
        **kwargs
    ) -> ControllerDecision:
        action = self.manual_commands.pop(junction_id, ACTION_EXTEND)
        return ControllerDecision(
            action=action,
            q_values=None,
            controller_name="manual",
            model_version=None,
            metadata={"manual": True}
        )
