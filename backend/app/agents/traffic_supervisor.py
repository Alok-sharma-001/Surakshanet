"""Traffic Operations Center (TOC) Autonomous Incident Commander and Multi-Agent Hierarchy.

Implements the Dual-Loop Cognitive ITS supervisory layer using the Google Antigravity SDK.
Orchestrates emergency corridor preemption, arterial congestion mitigation, and VMS public signage.
"""

import os
import logging
from typing import Optional, Dict, Any

from app.config import get_settings
from shared.constants import DataSource
from ml.marl.webster_fallback import WebsterFallback
from app.agent_tools.its_tools import (
    forecast_junction_traffic,
    clear_emergency_corridor,
    compute_optimal_reroute,
    query_nearby_junctions,
    broadcast_vms_advisory,
    get_junction_status,
)
from app.agent_tools.safety_guardrails import (
    validate_signal_plan_safety,
    enforce_safe_action_or_fallback,
)

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    from google.antigravity import Agent, LocalAgentConfig, LiteRTAgentConfig, types
    from google.antigravity.hooks import policy
    ANTIGRAVITY_AVAILABLE = True
except ImportError:
    ANTIGRAVITY_AVAILABLE = False
    logger.warning("google.antigravity is not installed or importable in current python runtime.")



# Subagent 1: Emergency Preemption Subagent
emergency_subagent = None
if ANTIGRAVITY_AVAILABLE:
    emergency_subagent = types.SubagentConfig(
        name="emergency_preemption_agent",
        description="Dedicated agent that handles ambulance, fire engine, and police green waves along arterial corridors.",
        tools=[clear_emergency_corridor, get_junction_status],
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
        ),
        system_instructions="""
        You are the Emergency Preemption Agent for Surakshanet.
        Your sole mission is to clear transit paths for approaching emergency vehicles (ambulances, fire engines, police).
        When triggered:
        1. Identify the corridor sequence of junctions.
        2. Activate green wave preemption immediately using clear_emergency_corridor.
        3. Confirm preemption hold status and notify the commander.
        Act with maximum urgency.
        """
    )


# Subagent 2: Arterial Congestion & Flow Subagent
congestion_subagent = None
if ANTIGRAVITY_AVAILABLE:
    congestion_subagent = types.SubagentConfig(
        name="arterial_congestion_agent",
        description="Dedicated agent that forecasts bottleneck spillbacks, inspects nearby networks, and calculates detour routes.",
        tools=[forecast_junction_traffic, compute_optimal_reroute, query_nearby_junctions, get_junction_status],
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
        ),
        system_instructions="""
        You are the Arterial Congestion Agent for Surakshanet.
        Your mission is to prevent gridlock spillback across urban junction networks.
        When congestion rises or accidents are reported:
        1. Call forecast_junction_traffic to evaluate 15/30/60 minute PCU projections.
        2. Query surrounding intersections using query_nearby_junctions to assess regional spillback risk.
        3. Compute optimal bypass detours using compute_optimal_reroute avoiding saturated nodes.
        4. Provide actionable recommendations to restore free flow.
        """
    )


# Subagent 3: Variable Message Sign (VMS) & Citizen Advisory Subagent
advisory_subagent = None
if ANTIGRAVITY_AVAILABLE:
    advisory_subagent = types.SubagentConfig(
        name="vms_advisory_agent",
        description="Dedicated agent for publishing driver detour notices and safety alerts to roadside NTCIP 1203 VMS boards.",
        tools=[broadcast_vms_advisory, get_junction_status],
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
        ),
        system_instructions="""
        You are the Public Advisory & VMS Agent for Surakshanet.
        Your mission is to inform drivers in real-time about upcoming bottlenecks, accidents, or emergency preemption.
        When dispatching notices:
        1. Format concise, high-visibility text conforming to standard 2-line roadside matrix displays (max 20 characters per line).
        2. Broadcast via broadcast_vms_advisory to upstream junctions.
        3. Set reasonable display expiration times (typically 15 to 30 minutes).
        """
    )


def create_supervisor_config(
    interactive: bool = False,
    api_key: Optional[str] = None
) -> "LocalAgentConfig":
    """Creates configuration for the root Incident Commander Agent."""
    if not ANTIGRAVITY_AVAILABLE:
        raise RuntimeError("google-antigravity SDK is not installed in the environment.")

    resolved_api_key = api_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

    behavior = types.AgentBehavior.INTERACTIVE if interactive else types.AgentBehavior.AUTONOMOUS

    # Subagents available to commander
    subagent_list = [s for s in [emergency_subagent, congestion_subagent, advisory_subagent] if s is not None]
    subagent_names = [s.name for s in subagent_list]

    all_tools = [
        forecast_junction_traffic,
        clear_emergency_corridor,
        compute_optimal_reroute,
        query_nearby_junctions,
        broadcast_vms_advisory,
        get_junction_status,
    ]

    policies_list = []
    try:
        policies_list = [
            policy.deny("run_command"),
            policy.allow_all(),
        ]
    except Exception:
        policies_list = []

    config_kwargs = {
        "tools": all_tools,
        "subagents": subagent_list,
        "capabilities": types.CapabilitiesConfig(
            agent_behavior=behavior,
            enable_subagents=True,
            max_subagent_depth=2,
            allowed_subagents=subagent_names,
        ),
        "policies": policies_list,
        "budget_config": types.BudgetConfig(
            max_model_calls=15,
            max_tool_calls=25,
            max_total_tokens=150_000,
        ),
        "retry_config": types.RetryConfig(
            api_retry=types.ModelAPIRetryConfig(
                max_retries=1,
                initial_sleep_duration_ms=400,
                exponential_multiplier=1.5,
            )
        ),
        "system_instructions": """
        You are the Surakshanet ITS Autonomous Incident Commander.
        You oversee the city's intelligent traffic network across all arterial corridors and intersections.

        Key Responsibilities:
        1. Monitor junction telemetry and diagnose network bottlenecks and safety anomalies.
        2. Supervise emergency corridors: When an ambulance or emergency vehicle approaches, coordinate green waves immediately.
        3. Mitigate congestion: Prevent queue spillbacks by forecasting traffic surges and planning detours.
        4. Public communication: Dispatch real-time notices to roadside Variable Message Signs (VMS).
        5. Delegate specialized tasks to your subagents:
           - emergency_preemption_agent for high-priority emergency vehicle clearance.
           - arterial_congestion_agent for forecasting and detour routing.
           - vms_advisory_agent for roadside dynamic signage updates.

        Always maintain strict safety principles: never violate minimum pedestrian clearances or conflicting signal interlocks.
        """
    }

    if resolved_api_key:
        config_kwargs["api_key"] = resolved_api_key

    return LocalAgentConfig(**config_kwargs)


def get_incident_commander_agent(interactive: bool = False, api_key: Optional[str] = None):
    """Factory creating an active Agent session."""
    config = create_supervisor_config(interactive=interactive, api_key=api_key)
    return Agent(config=config)


class ResilientTrafficSupervisor:
    """Supervises traffic decisions with automatic 3-tier fallback upon network loss or error."""

    def __init__(
        self,
        cloud_model: str = "gemini-3.7-flash",
        local_weights_path: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        self.cloud_model = cloud_model
        self.local_weights_path = local_weights_path or os.environ.get("LITERT_MODEL_PATH")
        self.api_key = api_key or settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.webster_fallback = WebsterFallback()
        self.active_tier = "tier_1_cloud" if (ANTIGRAVITY_AVAILABLE and self.api_key) else "tier_3_deterministic_webster"

        self.cloud_config = None
        if ANTIGRAVITY_AVAILABLE and self.api_key:
            try:
                self.cloud_config = create_supervisor_config(
                    interactive=False,
                    api_key=self.api_key
                )
            except Exception as err:
                logger.warning(f"Could not initialize cloud agent config: {err}")

    async def decide_signal_action(self, junction_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Decides optimal signal timing or preemption using the 3-tier fallback strategy."""

        # Safety Interlock Guardrail Pre-Check: Prevent unsafe timing plans
        if "ns_green" in context or "ew_green" in context or "yellow" in context:
            plan_to_test = {
                "ns_green": float(context.get("ns_green", 35.0)),
                "ew_green": float(context.get("ew_green", 35.0)),
                "yellow": float(context.get("yellow", 3.0)),
            }
            safety_eval = enforce_safe_action_or_fallback(plan_to_test)
            if safety_eval.get("source") == "WEBSTER_SAFETY_FALLBACK":
                logger.warning(
                    f"Physical safety constraint violated in signal plan for {junction_id}: "
                    f"{safety_eval.get('violations_prevented')}. Enforcing Webster Fallback."
                )
                self.active_tier = "tier_3_deterministic_webster"
                return {
                    "source": DataSource.HEURISTIC.value,
                    "tier": "tier_3_deterministic_webster",
                    "junction_id": junction_id,
                    "phase_string": "rrrrGGGggrrrrGGGgg",
                    "applied_plan": safety_eval.get("applied_plan"),
                    "status": "SAFETY_INTERLOCK_OVERRIDE",
                    "violations_prevented": safety_eval.get("violations_prevented"),
                    "reason": "Proposed timings violated minimum green, yellow clearance, or cycle bounds."
                }


        # --- TIER 1: Attempt Cloud Gemini Agent ---
        if ANTIGRAVITY_AVAILABLE and self.cloud_config:
            try:
                async with Agent(config=self.cloud_config) as cloud_agent:
                    prompt = (
                        f"Optimize signal for junction '{junction_id}'. "
                        f"Current traffic state: {context}. "
                        "Return recommendation for green allocation and cycle length."
                    )
                    response = await cloud_agent.chat(prompt)
                    action_text = await response.text()
                    self.active_tier = "tier_1_cloud"
                    return {
                        "source": DataSource.MODEL.value,
                        "tier": "tier_1_cloud",
                        "junction_id": junction_id,
                        "action": action_text,
                        "status": "AI_RECOMMENDATION_UNVALIDATED",
                        "validated": False,
                        "note": "Free-text LLM recommendation, not a parsed signal plan. Must be "
                                 "converted to explicit ns_green/ew_green/yellow values and pass "
                                 "validate_signal_plan_safety() before it may be applied to any "
                                 "signal controller."
                    }
            except Exception as net_err:
                logger.warning(
                    f"Tier 1 Cloud Agent unavailable or encountered error ({net_err}). "
                    "Degrading to Tier 2 Local Edge Agent..."
                )

        # --- TIER 2: Attempt On-Device LiteRT Edge Agent ---
        if ANTIGRAVITY_AVAILABLE and self.local_weights_path and os.path.exists(self.local_weights_path):
            try:
                local_config = LiteRTAgentConfig(
                    model_path=self.local_weights_path,
                    system_instructions="You are Surakshanet Edge Signal Controller running locally on LiteRT."
                )
                async with Agent(config=local_config) as edge_agent:
                    prompt = f"Local optimization for {junction_id} with state: {context}"
                    response = await edge_agent.chat(prompt)
                    action_text = await response.text()
                    self.active_tier = "tier_2_edge_litert"
                    return {
                        "source": DataSource.MODEL.value,
                        "tier": "tier_2_edge_litert",
                        "junction_id": junction_id,
                        "action": action_text,
                        "status": "AI_RECOMMENDATION_UNVALIDATED",
                        "validated": False,
                        "note": "Free-text LLM recommendation, not a parsed signal plan. Must be "
                                 "converted to explicit ns_green/ew_green/yellow values and pass "
                                 "validate_signal_plan_safety() before it may be applied to any "
                                 "signal controller."
                    }
            except Exception as edge_err:
                logger.error(
                    f"Tier 2 Edge LiteRT agent failed ({edge_err}). "
                    "Degrading to Tier 3 Hard Deterministic Baseline..."
                )

        # --- TIER 3: Deterministic Hard Real-Time Webster Baseline ---
        logger.info(f"Executing Tier 3 Webster Fallback for junction '{junction_id}'.")
        self.active_tier = "tier_3_deterministic_webster"
        plan = self.webster_fallback.get_current_plan()
        return {
            "source": DataSource.HEURISTIC.value,
            "tier": "tier_3_deterministic_webster",
            "junction_id": junction_id,
            "phase_string": "rrrrGGGggrrrrGGGgg",
            "applied_plan": plan,
            "status": "FAILSAFE_ACTIVE",
            "reason": "Cloud and Edge AI layers offline or bypassed; Webster time-of-day plan enforced."
        }

    def get_active_tier(self) -> str:
        """Returns the currently active operational tier."""
        return self.active_tier
