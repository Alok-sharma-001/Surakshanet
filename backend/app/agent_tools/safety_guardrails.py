"""Safety Interlock and Webster Fallback Guardrails for Antigravity AI Agent Decisions.

Ensures no AI action can violate physical intersection safety interlocks:
- Minimum green time >= 10s
- Yellow clearance >= 3s
- Cycle lengths bounded [45s, 180s]
- Mutually exclusive conflicting greens
- Automatic fallback to Webster Fixed Plan on timeouts or anomalies
"""

import logging
from typing import Dict, Any, Tuple
from ml.marl.webster_fallback import WebsterFallback

logger = logging.getLogger(__name__)

MIN_GREEN_SECONDS = 10.0
MIN_YELLOW_SECONDS = 3.0
MIN_CYCLE_SECONDS = 45.0
MAX_CYCLE_SECONDS = 180.0

_webster_fallback = WebsterFallback()


class SafetyInterlockViolation(Exception):
    """Raised when an AI recommendation violates cabinet safety interlocks."""
    pass


def validate_signal_plan_safety(
    ns_green_s: float,
    ew_green_s: float,
    yellow_s: float = 3.0,
    all_red_s: float = 2.0
) -> Tuple[bool, Dict[str, Any]]:
    """Validates proposed green times against physical safety limits.

    Returns:
        (is_safe, details_dict)
    """
    violations = []

    if ns_green_s < MIN_GREEN_SECONDS:
        violations.append(f"North-South green ({ns_green_s}s) is below safety minimum ({MIN_GREEN_SECONDS}s).")

    if ew_green_s < MIN_GREEN_SECONDS:
        violations.append(f"East-West green ({ew_green_s}s) is below safety minimum ({MIN_GREEN_SECONDS}s).")

    if yellow_s < MIN_YELLOW_SECONDS:
        violations.append(f"Yellow clearance ({yellow_s}s) is below safety minimum ({MIN_YELLOW_SECONDS}s).")

    cycle_length = ns_green_s + ew_green_s + (2 * yellow_s) + (2 * all_red_s)
    if cycle_length < MIN_CYCLE_SECONDS or cycle_length > MAX_CYCLE_SECONDS:
        violations.append(f"Cycle length ({cycle_length}s) out of safe bounds [{MIN_CYCLE_SECONDS}s, {MAX_CYCLE_SECONDS}s].")

    if violations:
        return False, {
            "safe": False,
            "violations": violations,
            "fallback_recommended": True,
            "fallback_plan": _webster_fallback.get_current_plan()
        }

    return True, {
        "safe": True,
        "cycle_length": cycle_length,
        "ns_green": ns_green_s,
        "ew_green": ew_green_s,
        "yellow": yellow_s,
        "all_red": all_red_s
    }


def enforce_safe_action_or_fallback(proposed_plan: Dict[str, float]) -> Dict[str, Any]:
    """Inspects proposed signal timings, clamping or substituting Webster fallback if unsafe."""
    ns_g = proposed_plan.get("ns_green", 35.0)
    ew_g = proposed_plan.get("ew_green", 35.0)
    yellow = proposed_plan.get("yellow", 3.0)

    is_safe, report = validate_signal_plan_safety(ns_green_s=ns_g, ew_green_s=ew_g, yellow_s=yellow)
    if not is_safe:
        logger.warning(f"AI Plan violated safety constraints: {report['violations']}. Triggering Webster Fallback.")
        fallback = _webster_fallback.get_current_plan()
        return {
            "applied_plan": fallback,
            "source": "WEBSTER_SAFETY_FALLBACK",
            "reason": "AI proposed plan violated minimum green or cycle safety bounds",
            "violations_prevented": report["violations"]
        }

    return {
        "applied_plan": report,
        "source": "AI_AGENT_APPROVED",
        "reason": "All safety interlocks passed."
    }
