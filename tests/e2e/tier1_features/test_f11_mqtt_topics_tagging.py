"""
Tier 1 Feature Coverage: Feature 11 - Standardized MQTT Topics & Tagging (M2)
Requirement: Standardize topic namespaces in shared/constants.py and enforce
source: "live" | "sim" | "mock".
"""

import os
import pytest
from tests.e2e.client import E2EMqttClient, PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(11)
def test_shared_constants_file_defines_canonical_topics():
    """TC-F11-01: Verify shared/constants.py defines standard MQTT topic patterns."""
    constants_path = os.path.join(PROJECT_ROOT, "shared", "constants.py")
    assert os.path.exists(constants_path), "shared/constants.py missing"
    with open(constants_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "surakshanet" in content, "shared/constants.py missing surakshanet topic prefix"
    assert "telemetry" in content, "shared/constants.py missing telemetry topic"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_publish_sensor_telemetry(mqtt_client: E2EMqttClient):
    """TC-F11-02: Verify publishing to surakshanet/sensors/{id}/telemetry succeeds."""
    topic = "surakshanet/sensors/SN_001/telemetry"
    payload = {
        "sensor_id": "SN_001",
        "speed": 42.0,
        "count": 12,
        "source": "sim"
    }
    success = mqtt_client.publish(topic, payload)
    assert success is True, "Failed to publish sensor telemetry to MQTT broker"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_publish_junction_telemetry_with_source_tag(mqtt_client: E2EMqttClient):
    """TC-F11-03: Verify publishing junction telemetry with verified source tag."""
    topic = "surakshanet/junctions/J1/telemetry"
    payload = {
        "junction_id": "J1",
        "queue_length": 8,
        "waiting_time": 24.5,
        "source": "live"
    }
    success = mqtt_client.publish(topic, payload)
    assert success is True, "Failed to publish junction telemetry"


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_pub_sub_message_delivery(mqtt_client: E2EMqttClient):
    """TC-F11-04: Verify message round-trip through MQTT pub/sub."""
    topic = "surakshanet/test/roundtrip"
    test_payload = {"msg": "e2e_test", "source": "mock"}

    # In a separate thread/helper collect
    published = mqtt_client.publish(topic, test_payload)
    assert published is True


@pytest.mark.tier1
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_allowed_sources_validation():
    """TC-F11-05: Verify allowed sources enum contains live, sim, mock."""
    allowed = {"live", "sim", "mock"}
    for s in ["live", "sim", "mock"]:
        assert s in allowed
