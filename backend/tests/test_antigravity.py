"""Unit tests for Google Antigravity SDK integration in Surakshanet ITS."""

import pytest
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
    MIN_GREEN_SECONDS,
    MIN_YELLOW_SECONDS,
)
from app.agents.traffic_supervisor import (
    create_supervisor_config,
    ResilientTrafficSupervisor,
)
from app.agents.incident_analyzer import TrafficIncidentReport
from app.api.copilot import (
    simulate_action,
    SimulationActionRequest,
    copilot_chat,
    CopilotChatRequest,
)


def test_forecast_junction_traffic():
    result = forecast_junction_traffic("j-silkboard")
    assert result["junction_id"] == "j-silkboard"
    assert "forecast_15m_pcu" in result
    assert "forecast_30m_pcu" in result
    assert "spillback_risk" in result
    if result["source"] == "unavailable":
        # No trained LSTM/XGBoost models in this environment — must be honest, not fabricated.
        assert result["forecast_15m_pcu"] is None
        assert result["spillback_risk"] is None
    else:
        assert result["source"] == "LSTM_XGBOOST_ENSEMBLE"
        assert 0.0 <= result["spillback_risk"] <= 1.0


def test_clear_emergency_corridor():
    # A real request through the shared EmergencyEvent/green-wave pathway never
    # claims "ACTIVE" — actual pre-emption depends on a live SUMO bridge being
    # connected, which this unit test does not have. It honestly reports
    # "requested" plus whether the bridge was actually notified.
    corridor = ["J0", "J1", "J2"]
    result = clear_emergency_corridor(corridor_junctions=corridor, vehicle_type="AMBULANCE", priority_level=1)
    assert result["status"] == "requested"
    assert result["priority_level"] == 1
    assert result["corridor"] == corridor
    assert "event_id" in result
    assert "bridge_notified" in result


def test_compute_optimal_reroute():
    result = compute_optimal_reroute(
        origin_lat=12.9176,
        origin_lon=77.6238,
        destination_lat=12.9756,
        destination_lon=77.6066,
        avoid_junction_ids=["j-silkboard"]
    )
    assert result["status"] == "COMPUTED"
    assert "j-silkboard" in result["avoided_junctions"]
    assert result["total_distance_km"] > 0
    assert result["estimated_travel_time_min"] > 0


def test_query_nearby_junctions():
    # Queries the real junctions table (never a hardcoded landmark list) —
    # these coordinates match the seeded "Bangalore Silk Board" junction.
    nearby = query_nearby_junctions(latitude=12.9176, longitude=77.6238, radius_meters=3000.0)
    assert isinstance(nearby, list)
    assert len(nearby) > 0
    # The seeded junction at these exact coordinates should be first (closest)
    assert nearby[0]["name"] == "Bangalore Silk Board"
    assert nearby[0]["distance_meters"] < 100.0


def test_broadcast_vms_advisory():
    result = broadcast_vms_advisory(
        junction_id="j-tin-factory",
        message_line_1="CRASH AHEAD SLOW",
        message_line_2="USE ORR DETOUR",
        duration_minutes=20
    )
    assert result["status"] == "PUBLISHED"
    assert result["junction_id"] == "j-tin-factory"
    assert result["display_line_1"] == "CRASH AHEAD SLOW"
    assert result["duration_minutes"] == 20


def test_get_junction_status():
    # Queries the real junctions/traffic_readings/control_decisions tables for
    # a seeded corridor junction. It must never report a plausible-looking
    # fixed number when nothing has actually been measured — the demo DB has
    # no simulation-generated readings for this junction, so an honest
    # "no_recent_data" status with null fields is the CORRECT result here,
    # not a failure.
    status = get_junction_status("J0")
    assert status["junction_name"] == "J0"
    assert status["status"] in ("ok", "no_recent_data")
    if status["status"] == "no_recent_data":
        assert status["current_pcu"] is None
    else:
        assert status["current_pcu"] > 0
    assert "current_phase" in status


def test_get_junction_status_unknown_junction_is_honest_not_found():
    status = get_junction_status("j-does-not-exist")
    assert status["status"] == "not_found"


def test_safety_guardrails_validation_success():
    is_safe, report = validate_signal_plan_safety(
        ns_green_s=40.0,
        ew_green_s=30.0,
        yellow_s=3.0,
        all_red_s=2.0
    )
    assert is_safe is True
    assert report["safe"] is True
    assert report["cycle_length"] == 40.0 + 30.0 + 6.0 + 4.0


def test_safety_guardrails_validation_violation():
    # Attempting to assign 5s green (violates MIN_GREEN_SECONDS=10s)
    is_safe, report = validate_signal_plan_safety(
        ns_green_s=5.0,
        ew_green_s=30.0,
        yellow_s=2.0
    )
    assert is_safe is False
    assert report["safe"] is False
    assert len(report["violations"]) >= 2
    assert report["fallback_recommended"] is True


def test_enforce_safe_action_fallback():
    unsafe_plan = {"ns_green": 4.0, "ew_green": 20.0, "yellow": 2.0}
    enforced = enforce_safe_action_or_fallback(unsafe_plan)
    assert enforced["source"] == "WEBSTER_SAFETY_FALLBACK"
    assert "applied_plan" in enforced


@pytest.fixture
async def client():
    """Fallback client fixture for isolated test execution when conftest is excluded."""
    try:
        from app.main import app
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
    except Exception:
        class MockClient:
            async def post(self, url, json=None):
                if "simulate-action" in url:
                    res = await simulate_action(SimulationActionRequest(**(json or {})))
                    class MockResponse:
                        status_code = 200
                        def json(self): return res
                    return MockResponse()
                elif "chat" in url:
                    res = await copilot_chat(CopilotChatRequest(**(json or {})))
                    class MockResponse:
                        status_code = 200
                        headers = {"content-type": getattr(res, "media_type", "application/json")}
                        def json(self):
                            if hasattr(res, "model_dump"):
                                return res.model_dump()
                            elif hasattr(res, "dict"):
                                return res.dict()
                            return res
                        async def aiter_lines(self):
                            if hasattr(res, "body_iterator"):
                                async for chunk in res.body_iterator:
                                    for line in chunk.split("\n"):
                                        if line:
                                            yield line
                        async def text(self):
                            if hasattr(res, "body_iterator"):
                                chunks = []
                                async for chunk in res.body_iterator:
                                    chunks.append(chunk)
                                return "".join(chunks)
                            return str(res)
                    return MockResponse()
                elif "analyze-snapshot" in url:
                    from app.api.copilot import analyze_snapshot, SnapshotAnalysisRequest
                    res = await analyze_snapshot(SnapshotAnalysisRequest(**(json or {})))
                    class MockResponse:
                        status_code = 200
                        def json(self):
                            return res.model_dump() if hasattr(res, "model_dump") else res.dict()
                    return MockResponse()
                raise NotImplementedError(url)
        yield MockClient()


@pytest.mark.asyncio
async def test_copilot_simulate_action_api(client):
    # This endpoint only requests the real emergency-corridor activation — it
    # never fabricates a delay-reduction percentage or a "safety interlocks
    # validated" claim nothing here actually checked.
    response = await client.post("/api/v1/copilot/simulate-action", json={
        "action_type": "PREEMPT_CORRIDOR",
        "corridor_junctions": ["J0", "J1"]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["simulation_type"] == "PREEMPTION_CORRIDOR_EVALUATION"
    assert "predicted_delay_reduction_pct" not in data
    assert "safety_interlocks_validated" not in data
    assert data["cabinet_details"]["status"] == "requested"


@pytest.mark.asyncio
async def test_copilot_chat_api(client):
    response = await client.post("/api/v1/copilot/chat", json={
        "message": "Status report on Silk Board junction",
        "junction_id": "j-silkboard",
        "stream": False
    })
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["status"] in ["success", "fallback"]


def test_resilient_traffic_supervisor_initialization():
    supervisor = ResilientTrafficSupervisor()
    assert supervisor.get_active_tier() in ["tier_1_cloud", "tier_3_deterministic_webster"]
    assert supervisor.webster_fallback is not None


@pytest.mark.asyncio
async def test_resilient_traffic_supervisor_tier3_fallback():
    supervisor = ResilientTrafficSupervisor(api_key="mock_invalid_key")
    # Bypass cloud config to test Tier 3 hard baseline
    supervisor.cloud_config = None
    result = await supervisor.decide_signal_action("j-silkboard", {"congestion": 0.85})
    assert result["tier"] == "tier_3_deterministic_webster"
    assert result["status"] == "FAILSAFE_ACTIVE"
    # No hardcoded phase string — a real per-topology TraCI phase string is
    # not knowable from this unit test's context, so applied_plan (the real
    # Webster ns_green/ew_green/cycle plan) is what is asserted instead.
    assert "phase_string" not in result
    assert "applied_plan" in result
    assert "ns_green" in result["applied_plan"]
    assert "ew_green" in result["applied_plan"]


def test_supervisor_config_structure():
    cfg = create_supervisor_config()
    assert len(cfg.tools) >= 6
    assert len(cfg.subagents) == 3
    subagent_names = {s.name for s in cfg.subagents}
    assert "emergency_preemption_agent" in subagent_names
    assert "arterial_congestion_agent" in subagent_names
    assert "vms_advisory_agent" in subagent_names


def test_traffic_incident_report_schema():
    report = TrafficIncidentReport(
        junction_id="j-silkboard",
        incident_type="COLLISION",
        severity="CRITICAL",
        confidence=0.92,
        lanes_blocked=2,
        estimated_pcu_impact=450.0,
        requires_emergency_dispatch=True,
        dispatch_units=["AMBULANCE", "POLICE"],
        recommended_vms_advisory="ACCIDENT ON CORRIDOR",
        tactical_recommendation="Preempt green wave and detour traffic."
    )
    assert report.junction_id == "j-silkboard"
    assert report.severity == "CRITICAL"
    assert report.requires_emergency_dispatch is True


@pytest.mark.asyncio
async def test_copilot_simulate_action_direct():
    req = SimulationActionRequest(
        action_type="PREEMPT_CORRIDOR",
        corridor_junctions=["J0", "J1"]
    )
    result = await simulate_action(req)
    assert result["simulation_type"] == "PREEMPTION_CORRIDOR_EVALUATION"
    # No independent evaluation runs here, so no unvalidated predictive/safety
    # claims may appear in the response.
    assert "predicted_delay_reduction_pct" not in result
    assert "safety_interlocks_validated" not in result


@pytest.mark.asyncio
async def test_copilot_simulate_action_direct_requires_corridor():
    # A corridor must never be assumed from a hardcoded default.
    req = SimulationActionRequest(action_type="PREEMPT_CORRIDOR")
    try:
        from fastapi import HTTPException
    except ImportError:
        from app.api.copilot import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await simulate_action(req)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_copilot_simulate_detour_direct():
    req = SimulationActionRequest(
        action_type="DETOUR_REROUTE",
        origin_lat=12.9176, origin_lon=77.6238,
        dest_lat=12.9756, dest_lon=77.6066,
        avoid_junctions=["j-tin-factory"]
    )
    result = await simulate_action(req)
    assert result["simulation_type"] == "DYNAMIC_REROUTE_EVALUATION"
    assert "j-tin-factory" in result["avoided_chokepoints"]


@pytest.mark.asyncio
async def test_copilot_simulate_detour_direct_requires_coordinates():
    # An origin/destination must never be silently defaulted to a fixed
    # location — that was the exact anti-pattern SN-049 exists to eliminate.
    req = SimulationActionRequest(action_type="DETOUR_REROUTE", avoid_junctions=["j-tin-factory"])
    try:
        from fastapi import HTTPException
    except ImportError:
        from app.api.copilot import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await simulate_action(req)
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_copilot_chat_streaming_sse():
    """Validates SSE streaming delivery of reasoning and conversational tokens."""
    req = CopilotChatRequest(
        message="Simulate emergency clearance",
        junction_id="j-silkboard",
        stream=True
    )
    response = await copilot_chat(req)
    assert hasattr(response, "body_iterator")
    assert response.media_type == "text/event-stream"

    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk)

    full_stream = "".join(chunks)
    assert "data: " in full_stream
    assert "[DONE]" in full_stream


@pytest.mark.asyncio
async def test_resilient_traffic_supervisor_safety_interlock_override():
    """Validates physical safety interlock enforcement when AI/context proposes unsafe timings."""
    supervisor = ResilientTrafficSupervisor()
    # Proposed timing violates minimum green (ns_green=4.0s < 10.0s) and yellow clearance (yellow=1.5s < 3.0s)
    unsafe_context = {
        "ns_green": 4.0,
        "ew_green": 20.0,
        "yellow": 1.5
    }
    result = await supervisor.decide_signal_action("j-silkboard", unsafe_context)
    assert result["status"] == "SAFETY_INTERLOCK_OVERRIDE"
    assert result["tier"] == "tier_3_deterministic_webster"
    # No hardcoded phase string — see test_resilient_traffic_supervisor_tier3_fallback.
    assert "phase_string" not in result
    assert len(result["violations_prevented"]) >= 2
    assert "applied_plan" in result
    assert "ns_green" in result["applied_plan"]


def test_supervisor_policies_and_budgets():
    """Validates that Antigravity policies and session budgets are properly attached."""
    cfg = create_supervisor_config()
    assert hasattr(cfg, "policies")
    assert len(cfg.policies) >= 2
    assert hasattr(cfg, "budget_config")
    assert cfg.budget_config.max_model_calls == 15
    assert cfg.budget_config.max_tool_calls == 25


def test_resilient_supervisor_tools_bound():
    """Validates that ResilientTrafficSupervisor equips cloud agents with tools and subagents."""
    supervisor = ResilientTrafficSupervisor()
    if supervisor.cloud_config:
        assert len(supervisor.cloud_config.tools) >= 6
        assert len(supervisor.cloud_config.subagents) == 3


@pytest.mark.asyncio
async def test_copilot_analyze_snapshot_demo_path_is_not_special_cased(client):
    """A snapshot path that merely LOOKS like a demo/sample path must never be
    fabricated into a plausible-looking incident report — a missing file is a
    404 regardless of what its path contains. (This endpoint previously had a
    special-cased "demo path" fallback that fabricated a fake NORMAL_FLOW
    report; that fallback has been removed as a fabrication defect.)
    """
    response = await client.post("/api/v1/copilot/analyze-snapshot", json={
        "image_path": "/opt/surakshanet/cctv_snapshots/frame_0842.jpg",
        "junction_id": "j-silkboard"
    })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_copilot_analyze_snapshot_missing_file_404():
    """Validates 404 error when an unrecognized local image file path is passed."""
    from app.api.copilot import analyze_snapshot, SnapshotAnalysisRequest
    try:
        from fastapi import HTTPException
    except ImportError:
        from app.api.copilot import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await analyze_snapshot(SnapshotAnalysisRequest(
            image_path="/tmp/non_existent_file_xyz123.jpg",
            junction_id="j-silkboard"
        ))
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_analyze_junction_camera_snapshot_real_frame(tmp_path):
    """Validates multimodal frame analyzer with an actual generated image file."""
    from app.agents.incident_analyzer import analyze_junction_camera_snapshot
    # Write a minimal valid 1x1 PNG image
    sample_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    img_file = tmp_path / "test_frame.png"
    img_file.write_bytes(sample_png)

    report = await analyze_junction_camera_snapshot(
        image_path=str(img_file),
        junction_id="j-silkboard"
    )
    assert isinstance(report, TrafficIncidentReport)
    assert report.junction_id == "j-silkboard"
    assert report.confidence >= 0.0

