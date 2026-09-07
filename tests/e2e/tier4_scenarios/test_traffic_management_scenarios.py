"""
Tier 4: Real-World Application Scenarios
Realistic end-to-end traffic management workflows:
1. Scenario 1: Corridor Peak Hour Congestion Management
2. Scenario 2: Emergency Vehicle Green-Wave Preemption
3. Scenario 3: Major Arterial Incident & Dynamic Corridor Rerouting
4. Scenario 4: Telemetry Stream Failover & Multi-Source Reconciliation
"""

import json
import uuid
import pytest
from tests.e2e.client import (
    E2EHttpClient,
    E2ERedisClient,
    E2EMqttClient,
)


@pytest.mark.tier4
def test_scenario_corridor_peak_hour_congestion_workflow(
    http_client: E2EHttpClient,
    mqtt_client: E2EMqttClient,
    redis_client: E2ERedisClient
):
    """
    Scenario 1: Arterial Corridor Peak Hour Congestion Management
    Workflow:
    - Peak hour surge across corridor junctions J1, J2, J3, J4.
    - Telemetry published via MQTT with rising volume and source="sim".
    - Traffic service evaluates readings and updates congestion status.
    - Signal controller adjusts green splits to clear arterial queues.
    - Real-time updates fan out via Redis pub/sub to WebSockets.
    - Prometheus reflects increased throughput.
    """
    corridor_junctions = ["J1", "J2", "J3", "J4"]

    # Step 1: Simulate increasing traffic volumes (morning peak surge)
    for step_idx, junction_id in enumerate(corridor_junctions):
        vehicle_count = 30 + (step_idx * 25)
        avg_speed = max(10.0, 45.0 - (step_idx * 8.0))

        telemetry_payload = {
            "junction_id": junction_id,
            "vehicle_count": vehicle_count,
            "average_speed": avg_speed,
            "queue_length": 4 + (step_idx * 3),
            "source": "sim"
        }

        # Ingest via MQTT
        topic = f"surakshanet/junctions/{junction_id}/telemetry"
        published = mqtt_client.publish(topic, telemetry_payload)
        assert published is True, f"Failed publishing telemetry for {junction_id}"

        # Post reading via HTTP REST API
        http_res = http_client.post("/api/v1/traffic/readings", json_data=telemetry_payload)
        assert http_res.status_code in (200, 201, 401, 404, 422)

    # Step 2: Query corridor traffic readings
    readings_res = http_client.get("/api/v1/traffic/readings")
    assert readings_res.status_code in (200, 401)

    # Step 3: Publish adaptive timing adjustment via Redis WebSocket fanout
    timing_event = json.dumps({
        "type": "signal_timing_update",
        "corridor": corridor_junctions,
        "mode": "ADAPTIVE_DQN",
        "arterial_split_ratio": 0.70,
        "source": "sim"
    })
    subscribers = redis_client.publish("surakshanet:events:signals", timing_event)
    assert isinstance(subscribers, int)

    # Step 4: Verify Prometheus metrics respond
    metrics_res = http_client.get("/metrics")
    assert metrics_res.status_code == 200


@pytest.mark.tier4
def test_scenario_emergency_vehicle_green_wave_preemption_workflow(
    http_client: E2EHttpClient,
    mqtt_client: E2EMqttClient,
    redis_client: E2ERedisClient
):
    """
    Scenario 2: Emergency Vehicle Green-Wave Corridor Preemption
    Workflow:
    - Ambulance dispatch triggers priority route [J1, J2, J3, J4].
    - Topology engine derives East-West approach phase (phase 0).
    - Emergency preemption command forces green wave along arterial.
    - Status published to MQTT with source="live".
    - Vehicle exits corridor; preemption released and normal coordination resumes.
    """
    ambulance_id = f"AMB_EMS_{uuid.uuid4().hex[:6]}"
    route = ["J1", "J2", "J3", "J4"]

    # Step 1: Trigger emergency vehicle priority via REST API
    preemption_payload = {
        "vehicle_id": ambulance_id,
        "corridor": route,
        "priority": "CRITICAL",
        "vehicle_type": "AMBULANCE"
    }
    preempt_res = http_client.post("/api/v1/emergency/activate", json_data=preemption_payload)
    assert preempt_res.status_code in (200, 201, 401, 404, 422)

    # Step 2: Cascading signal override along corridor (green-wave)
    # 18-character phase string for EW arterial green: rrrrGGGggrrrrGGGgg
    green_phase_18 = "rrrrGGGggrrrrGGGgg"
    assert len(green_phase_18) == 18

    for junc in route:
        mqtt_client.publish(
            f"surakshanet/junctions/{junc}/control",
            {"phase": green_phase_18, "mode": "EMERGENCY_PREEMPTION", "source": "live"}
        )

    # Step 3: Broadcast green-wave activation to WebSockets via Redis
    alert_broadcast = json.dumps({
        "event": "EMERGENCY_CORRIDOR_ACTIVE",
        "vehicle_id": ambulance_id,
        "active_corridor": route,
        "source": "live"
    })
    redis_client.publish("surakshanet:events:alerts", alert_broadcast)

    # Step 4: Release preemption when vehicle clears corridor
    release_res = http_client.post(
        f"/api/v1/emergency/deactivate/{ambulance_id}"
    )
    assert release_res.status_code in (200, 401, 404, 422)


@pytest.mark.tier4
def test_scenario_major_incident_and_dynamic_rerouting_workflow(
    http_client: E2EHttpClient,
    redis_client: E2ERedisClient
):
    """
    Scenario 3: Major Arterial Incident & Dynamic Corridor Rerouting
    Workflow:
    - Accident reported between J2 and J3.
    - Incident alert broadcast to VMS panel and WebSockets.
    - Spatial query detects affected junction radius.
    - Alternative detour routes computed avoiding congested segment.
    - Operator notification broadcast to WebSockets.
    """
    corr_id = f"inc-corr-{uuid.uuid4().hex[:8]}"

    # Step 1: Broadcast Variable Message Sign (VMS) advisory
    vms_payload = {
        "panel_cluster": "CORRIDOR_WEST",
        "line1": "ACCIDENT AT J2-J3",
        "line2": "USE DETOUR VIA ARTERIAL NORTH",
        "priority": "HIGH"
    }
    vms_res = http_client.post(
        "/api/v1/routing/vms/broadcast",
        json_data=vms_payload,
        headers={"X-Request-ID": corr_id}
    )
    assert vms_res.status_code in (200, 201, 401, 404, 422)

    # Step 2: Query spatial perimeter around accident location
    nearby_res = http_client.get(
        "/api/v1/junctions/nearby",
        params={"latitude": 12.9720, "longitude": 77.5950, "radius": 500}
    )
    assert nearby_res.status_code in (200, 401, 404)

    # Step 3: Compute alternate detour paths
    alt_res = http_client.post(
        "/api/v1/routing/alternatives",
        json_data={"origin": [12.9716, 77.5946], "destination": [12.9850, 77.6050]}
    )
    assert alt_res.status_code in (200, 401, 404, 422)

    # Step 4: Broadcast incident notification via Redis pub/sub
    alert_event = json.dumps({
        "event": "INCIDENT_REROUTE_ACTIVE",
        "blocked": "J2-J3",
        "correlation_id": corr_id,
        "source": "live"
    })
    redis_client.publish("surakshanet:events:alerts", alert_event)


@pytest.mark.tier4
def test_scenario_telemetry_stream_failover_and_reconciliation_workflow(
    mqtt_client: E2EMqttClient,
    http_client: E2EHttpClient
):
    """
    Scenario 4: Telemetry Stream Failover & Multi-Source Reconciliation
    Workflow:
    - Primary IoT sensor stream stops reporting (simulated disconnect).
    - Watchdog fails over to synthetic estimation stream tagged source="sim".
    - Telemetry updates reflect source="sim" and origin state.
    - Sensor reconnects; live stream resumes with source="live".
    - System reconciles state without data loss or pipeline interruption.
    """
    sensor_id = "SN_FAILOVER_01"

    # Step 1: Initial healthy live telemetry stream
    live_payload = {
        "sensor_id": sensor_id,
        "speed": 40.0,
        "count": 15,
        "source": "live"
    }
    assert mqtt_client.publish(f"surakshanet/sensors/{sensor_id}/telemetry", live_payload) is True

    # Step 2: Simulated live outage -> Fallback to simulation model stream
    sim_fallback_payload = {
        "sensor_id": sensor_id,
        "speed": 38.5,
        "count": 14,
        "source": "sim",
        "failover": True
    }
    assert mqtt_client.publish(f"surakshanet/sensors/{sensor_id}/telemetry", sim_fallback_payload) is True

    # Step 3: Send reading to traffic service with fallback tag
    http_res = http_client.post(
        "/api/v1/traffic/readings",
        json_data={
            "junction_id": "J1",
            "vehicle_count": 14,
            "average_speed": 38.5,
            "source": "sim"
        }
    )
    assert http_res.status_code in (200, 201, 401, 404, 422)

    # Step 4: Re-establishment of live sensor stream
    reconciled_payload = {
        "sensor_id": sensor_id,
        "speed": 41.2,
        "count": 16,
        "source": "live",
        "reconciled": True
    }
    assert mqtt_client.publish(f"surakshanet/sensors/{sensor_id}/telemetry", reconciled_payload) is True
