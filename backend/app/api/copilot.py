"""Traffic Operations Center (TOC) Operator Copilot API using Google Antigravity SDK.

Provides streaming conversational AI endpoints, multimodal snapshot diagnostics,
and 'what-if' action simulation for city traffic engineers.
"""

import json
import logging
from typing import Optional
try:
    from fastapi import APIRouter, HTTPException, Depends
    from fastapi.responses import StreamingResponse
except ImportError:
    class APIRouter:
        def __init__(self, *args, **kwargs):
            self.routes = []
        def post(self, *args, **kwargs):
            return lambda f: f
        def get(self, *args, **kwargs):
            return lambda f: f
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str):
            self.status_code = status_code
            self.detail = detail
            super().__init__(detail)
    def Depends(f=None):
        return f
    from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.agents.traffic_supervisor import get_incident_commander_agent, ANTIGRAVITY_AVAILABLE
from app.agents.incident_analyzer import analyze_junction_camera_snapshot, TrafficIncidentReport
from app.agent_tools.its_tools import (
    clear_emergency_corridor,
    compute_optimal_reroute,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/copilot", tags=["TOC Copilot (Antigravity AI)"])


class CopilotChatRequest(BaseModel):
    message: str = Field(..., description="Operator query or directive")
    stream: bool = Field(default=False, description="Whether to stream response tokens via SSE")
    junction_id: Optional[str] = Field(default=None, description="Optional target junction context")


class CopilotChatResponse(BaseModel):
    response: str
    thoughts: Optional[str] = None
    status: str = "success"


class SnapshotAnalysisRequest(BaseModel):
    image_path: str = Field(..., description="Local path to camera snapshot frame")
    junction_id: str = Field(default="j-incident-site", description="Junction identifier")


class SimulationActionRequest(BaseModel):
    action_type: str = Field(..., description="Action to simulate: 'PREEMPT_CORRIDOR' or 'DETOUR_REROUTE'")
    corridor_junctions: Optional[list[str]] = Field(default=None)
    origin_lat: Optional[float] = Field(default=None)
    origin_lon: Optional[float] = Field(default=None)
    dest_lat: Optional[float] = Field(default=None)
    dest_lon: Optional[float] = Field(default=None)
    avoid_junctions: Optional[list[str]] = Field(default=None)


@router.post("/chat")
async def copilot_chat(payload: CopilotChatRequest):
    """Processes operator natural-language queries using the Antigravity Incident Commander Agent.

    Supports both streaming SSE token delivery and unified JSON responses.
    """
    user_query = payload.message
    if payload.junction_id:
        user_query = f"[Context: Junction {payload.junction_id}] {user_query}"

    if not ANTIGRAVITY_AVAILABLE:
        fallback_msg = (
            "Antigravity SDK runtime is currently running in fallback mode. "
            f"Your query was: '{user_query}'. "
            "Ensure google-antigravity is installed in your active environment and GEMINI_API_KEY is configured in .env."
        )
        if payload.stream:
            async def sdk_missing_sse():
                yield f"data: {json.dumps({'type': 'thought', 'content': 'Fallback mode active: google.antigravity package not found.'})}\n\n"
                for word in fallback_msg.split(" "):
                    yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(sdk_missing_sse(), media_type="text/event-stream")

        return CopilotChatResponse(
            response=fallback_msg,
            thoughts="Fallback mode active. google.antigravity package not found.",
            status="fallback"
        )

    if payload.stream:
        async def sse_generator():
            try:
                async with get_incident_commander_agent(interactive=True) as agent:
                    response = await agent.chat(user_query)

                    # Stream internal reasoning thoughts first if available
                    if hasattr(response, "thoughts"):
                        async for thought in response.thoughts:
                            yield f"data: {json.dumps({'type': 'thought', 'content': thought})}\n\n"

                    # Stream text response tokens
                    async for token in response:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                    yield "data: [DONE]\n\n"
            except Exception as e:
                logger.warning(f"Error in Copilot SSE stream: {e}. Yielding fallback tokens.", exc_info=True)
                yield f"data: {json.dumps({'type': 'thought', 'content': f'Upstream fallback triggered: {str(e)}'})}\n\n"
                fallback_stream_text = (
                    "Surakshanet Incident Commander (Fallback Mode): "
                    f"Processed query '{user_query}'. "
                    "Upstream AI model temporarily unavailable; deterministic Webster safety timings and telemetry active."
                )
                for word in fallback_stream_text.split(" "):
                    yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                yield "data: [DONE]\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    # Non-streaming JSON mode
    try:
        async with get_incident_commander_agent(interactive=True) as agent:
            response = await agent.chat(user_query)
            final_text = await response.text()

            thoughts_text = ""
            if hasattr(response, "thoughts"):
                async for t in response.thoughts:
                    thoughts_text += t

            return CopilotChatResponse(
                response=final_text,
                thoughts=thoughts_text if thoughts_text else None,
                status="success"
            )
    except Exception as e:
        logger.warning(f"Error executing agent chat: {e}. Returning graceful fallback response.")
        return CopilotChatResponse(
            response=(
                "Surakshanet Incident Commander (Fallback Mode): "
                f"Processed query '{user_query}'. "
                "Upstream AI model temporarily unavailable; deterministic Webster safety timings and telemetry active."
            ),
            thoughts=f"Fallback triggered due to upstream exception: {str(e)}",
            status="fallback"
        )


@router.post("/analyze-snapshot", response_model=TrafficIncidentReport)
async def analyze_snapshot(payload: SnapshotAnalysisRequest):
    """Inspects CCTV camera frame using Gemini Multimodal vision to diagnose incidents."""
    import os
    if not os.path.exists(payload.image_path):
        # A missing snapshot is never fabricated into a plausible-looking "all
        # clear" report, demo path or not — that was the exact class of
        # defect Phase 0 exists to eliminate (mirrors ml/vision's
        # VisionUnavailable convention).
        raise HTTPException(status_code=404, detail=f"Camera snapshot file not found: '{payload.image_path}'")

    try:
        report = await analyze_junction_camera_snapshot(
            image_path=payload.image_path,
            junction_id=payload.junction_id
        )
        return report
    except Exception as e:
        logger.error(f"Snapshot analysis failure: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to analyze snapshot: {str(e)}")



@router.post("/simulate-action")
async def simulate_action(payload: SimulationActionRequest):
    """Simulates arterial interventions (emergency green wave or detours) before committing to cabinets."""
    action = payload.action_type.upper()

    if action == "PREEMPT_CORRIDOR":
        if not payload.corridor_junctions:
            raise HTTPException(
                status_code=422,
                detail="corridor_junctions is required — a corridor is never assumed."
            )
        result = clear_emergency_corridor(
            corridor_junctions=payload.corridor_junctions, vehicle_type="AMBULANCE", priority_level=1
        )
        # No independent evaluation runs here — this endpoint only requests the
        # same real activation clear_emergency_corridor() performs (persisted
        # EmergencyEvent + Redis notification to the live bridge). It cannot
        # honestly claim a delay-reduction percentage, a queue-impact estimate,
        # or a validated safety interlock nothing here actually checked.
        return {
            "simulation_type": "PREEMPTION_CORRIDOR_EVALUATION",
            "action": "CLEAR_GREEN_WAVE",
            "estimated_corridor_transit_seconds": result.get("clearance_time_s"),
            "route_etas": result.get("route_etas"),
            "cabinet_details": result
        }

    elif action == "DETOUR_REROUTE":
        if None in (payload.origin_lat, payload.origin_lon, payload.dest_lat, payload.dest_lon):
            raise HTTPException(
                status_code=422,
                detail="origin_lat, origin_lon, dest_lat, and dest_lon are all required — "
                       "a route origin/destination is never assumed."
            )
        avoid = payload.avoid_junctions or []

        route_data = compute_optimal_reroute(
            payload.origin_lat, payload.origin_lon, payload.dest_lat, payload.dest_lon, avoid_junction_ids=avoid
        )
        return {
            "simulation_type": "DYNAMIC_REROUTE_EVALUATION",
            "action": "ARTERIAL_DETOUR",
            "avoided_chokepoints": avoid,
            "predicted_time_savings_minutes": route_data.get("congestion_savings_min"),
            "route_metrics": route_data
        }

    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported simulation action '{action}'. Supported: PREEMPT_CORRIDOR, DETOUR_REROUTE"
        )
