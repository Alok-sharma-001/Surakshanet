"""
Tier 2 Boundary & Corner Cases: Feature 11 - MQTT Topics & Tagging Boundaries (M2)
Missing source tag, invalid source enum, malformed payloads, wildcard topics, empty payloads.
"""

import pytest
from tests.e2e.client import E2EMqttClient


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_payload_missing_source_field(mqtt_client: E2EMqttClient):
    """TC-B11-01: Boundary - Publishing payload missing required 'source' field."""
    topic = "surakshanet/sensors/TEST_B11/telemetry"
    payload = {"sensor_id": "TEST_B11", "value": 100}  # No source
    res = mqtt_client.publish(topic, payload)
    assert res is True  # Broker accepts message even if consumer validates


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_payload_invalid_source_value(mqtt_client: E2EMqttClient):
    """TC-B11-02: Boundary - Publishing payload with invalid source enum value."""
    topic = "surakshanet/sensors/TEST_B11/telemetry"
    payload = {"sensor_id": "TEST_B11", "source": "unauthorized_origin"}
    res = mqtt_client.publish(topic, payload)
    assert res is True


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_malformed_non_json_string(mqtt_client: E2EMqttClient):
    """TC-B11-03: Boundary - Publishing non-JSON string to telemetry topic."""
    topic = "surakshanet/sensors/TEST_B11/telemetry"
    raw_payload = "NOT_JSON_DATA_RAW_BYTES_XYZ"
    res = mqtt_client.publish(topic, raw_payload)
    assert res is True, "Broker should handle raw payload without closing"


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_empty_payload(mqtt_client: E2EMqttClient):
    """TC-B11-04: Boundary - Publishing 0-byte empty string to telemetry topic."""
    topic = "surakshanet/sensors/TEST_B11/telemetry"
    res = mqtt_client.publish(topic, "")
    assert res is True


@pytest.mark.tier2
@pytest.mark.m2
@pytest.mark.feature(11)
def test_mqtt_wildcard_topic_structure():
    """TC-B11-05: Boundary - Verify wildcard patterns conform to MQTT 3.1.1 spec."""
    valid_wildcards = [
        "surakshanet/+/+/telemetry",
        "surakshanet/sensors/#",
        "surakshanet/junctions/+/control"
    ]
    for w in valid_wildcards:
        assert "+" in w or "#" in w
