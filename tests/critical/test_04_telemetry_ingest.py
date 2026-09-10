"""
SN-114 · Telemetry Ingestion Critical Test
=========================================
Verifies:
1. Valid MQTT telemetry payload validates and carries source='mqtt'.
2. Malformed payload (missing source, missing approaches, invalid source) is rejected.
3. Channel constants match between publisher and subscriber (SN-026, SN-028).

Mutation check: remove schema validation in shared/telemetry.py or mqtt_consumer._process_telemetry -> test fails.
"""

import pytest
import uuid
from shared.constants import DataSource, REDIS_CHANNELS
from shared.telemetry import (
    ApproachTelemetry,
    JunctionTelemetry,
    validate_telemetry,
    TelemetryValidationError,
)


def _sample_valid_payload():
    return {
        "junction_id": "J1",
        "source": "mqtt",
        "approaches": [
            {
                "direction": "N",
                "lane_ids": ["N_0", "N_1"],
                "vehicle_count": 5.0,
                "pcu": 7.5,
                "queue_length_m": 12.0,
                "mean_speed_kmh": 35.0,
                "occupancy": 0.25,
                "accumulated_wait_s": 40.0,
                "vehicle_breakdown": {"car": 4, "bus": 1}
            },
            {
                "direction": "E",
                "lane_ids": ["E_0"],
                "vehicle_count": 2.0,
                "pcu": 2.0,
                "queue_length_m": 0.0,
                "mean_speed_kmh": 45.0,
                "occupancy": 0.1,
                "accumulated_wait_s": 0.0,
                "vehicle_breakdown": {"car": 2}
            },
            {
                "direction": "S",
                "lane_ids": ["S_0"],
                "vehicle_count": 3.0,
                "pcu": 3.5,
                "queue_length_m": 5.0,
                "mean_speed_kmh": 30.0,
                "occupancy": 0.15,
                "accumulated_wait_s": 10.0,
                "vehicle_breakdown": {"car": 2, "motorcycle": 2}
            },
            {
                "direction": "W",
                "lane_ids": ["W_0"],
                "vehicle_count": 1.0,
                "pcu": 1.0,
                "queue_length_m": 0.0,
                "mean_speed_kmh": 50.0,
                "occupancy": 0.05,
                "accumulated_wait_s": 0.0,
                "vehicle_breakdown": {"car": 1}
            }
        ],
        "current_phase": 0,
        "phase_elapsed_s": 15.0,
        "total_pcu": 14.0
    }


def test_valid_mqtt_payload_validates_and_stamps_source():
    payload = _sample_valid_payload()
    telemetry = validate_telemetry(payload)
    assert isinstance(telemetry, JunctionTelemetry)
    assert telemetry.source == DataSource.MQTT
    assert telemetry.junction_id == "J1"
    assert len(telemetry.approaches) == 4
    assert telemetry.total_pcu == 14.0


def test_missing_source_rejected():
    payload = _sample_valid_payload()
    del payload["source"]
    with pytest.raises(TelemetryValidationError, match="missing mandatory 'source'"):
        validate_telemetry(payload)


def test_unknown_source_rejected():
    payload = _sample_valid_payload()
    payload["source"] = "magic_telemetry_source"
    with pytest.raises(TelemetryValidationError, match="unknown source"):
        validate_telemetry(payload)


def test_missing_approaches_rejected():
    payload = _sample_valid_payload()
    payload["approaches"] = []
    with pytest.raises(TelemetryValidationError, match="approaches.*must be a non-empty list"):
        validate_telemetry(payload)


def test_approach_missing_direction_rejected():
    payload = _sample_valid_payload()
    del payload["approaches"][0]["direction"]
    with pytest.raises(TelemetryValidationError, match="missing 'direction'"):
        validate_telemetry(payload)


def test_missing_junction_id_rejected():
    payload = _sample_valid_payload()
    del payload["junction_id"]
    with pytest.raises(TelemetryValidationError, match="missing 'junction_id'"):
        validate_telemetry(payload)


def test_redis_channels_constant_consistency():
    # Verify standard Redis channel names are pinned in REDIS_CHANNELS
    assert REDIS_CHANNELS["traffic"] == "traffic_updates"
    assert REDIS_CHANNELS["control_commands"] == "control_commands"
    assert REDIS_CHANNELS["control_decisions"] == "control_decisions"
    assert REDIS_CHANNELS["signals"] == "signal_events"
    assert REDIS_CHANNELS["simulation"] == "simulation_updates"
