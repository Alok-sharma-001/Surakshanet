"""
SurakshaNet Canonical Telemetry Schema & Validation (SN-023)
===========================================================
Defines the canonical data model for all traffic telemetry producers
(SUMO live bridge, MQTT edge devices, and Vision worker).
Conforms to docs/07-telemetry.md §3 and §5.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Union
import uuid

from shared.constants import DataSource

logger = logging.getLogger("surakshanet.telemetry")


class TelemetryValidationError(ValueError):
    """Raised when a telemetry payload fails canonical schema validation."""
    pass


@dataclass
class ApproachTelemetry:
    direction: str                            # "N" | "E" | "S" | "W"
    lane_ids: List[str]
    vehicle_count: float
    pcu: float                                # PCU equivalent
    queue_length_m: float
    mean_speed_kmh: float
    occupancy: float                          # 0.0 - 1.0
    accumulated_wait_s: float
    vehicle_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApproachTelemetry":
        return cls(
            direction=str(data.get("direction", "")),
            lane_ids=list(data.get("lane_ids", [])),
            vehicle_count=float(data.get("vehicle_count", 0.0)),
            pcu=float(data.get("pcu", 0.0)),
            queue_length_m=float(data.get("queue_length_m", 0.0)),
            mean_speed_kmh=float(data.get("mean_speed_kmh", 0.0)),
            occupancy=float(data.get("occupancy", 0.0)),
            accumulated_wait_s=float(data.get("accumulated_wait_s", 0.0)),
            vehicle_breakdown=dict(data.get("vehicle_breakdown", {}))
        )


@dataclass
class JunctionTelemetry:
    junction_id: str                          # SUMO tl id (e.g. J0) or DB UUID
    source: DataSource                        # MANDATORY provenance
    approaches: List[ApproachTelemetry]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "1.0"
    sim_time_s: Optional[float] = None        # populated when source == sumo
    current_phase: int = 0
    phase_elapsed_s: float = 0.0
    cycle_length_s: Optional[float] = None
    controller: Optional[str] = None          # "marl" | "webster" | "manual" | None
    total_pcu: float = 0.0                    # sum over approaches
    seed: Optional[int] = None                # populated when source == sumo

    def __post_init__(self):
        if not self.total_pcu and self.approaches:
            self.total_pcu = sum(a.pcu for a in self.approaches)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(self.source, DataSource):
            d["source"] = self.source.value
        d["approaches"] = [a.to_dict() for a in self.approaches]
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JunctionTelemetry":
        return validate_telemetry(data)


def validate_telemetry(payload: Union[Dict[str, Any], str]) -> JunctionTelemetry:
    """
    Validates a telemetry payload against the canonical JunctionTelemetry schema.
    A payload missing 'source', missing 'approaches', or with an unknown source is
    rejected with TelemetryValidationError. Never partially written.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception as e:
            raise TelemetryValidationError(f"Invalid JSON payload: {e}") from e

    if not isinstance(payload, dict):
        raise TelemetryValidationError(f"Telemetry payload must be a dict, got {type(payload).__name__}")

    # 1. Validate mandatory source
    raw_source = payload.get("source")
    if not raw_source:
        logger.warning("Telemetry rejected: missing mandatory 'source' field.")
        raise TelemetryValidationError("Telemetry rejected: missing mandatory 'source' field.")

    if isinstance(raw_source, DataSource):
        source_enum = raw_source
    else:
        try:
            source_enum = DataSource(str(raw_source).lower())
        except ValueError:
            logger.warning(f"Telemetry rejected: unknown source '{raw_source}'.")
            raise TelemetryValidationError(
                f"Telemetry rejected: unknown source '{raw_source}'. Must be one of {[s.value for s in DataSource]}"
            )

    # 2. Validate mandatory approaches
    raw_approaches = payload.get("approaches")
    if not raw_approaches or not isinstance(raw_approaches, list) or len(raw_approaches) == 0:
        logger.warning(f"Telemetry rejected for {payload.get('junction_id')}: missing or empty 'approaches'.")
        raise TelemetryValidationError("Telemetry rejected: 'approaches' must be a non-empty list.")

    approaches: List[ApproachTelemetry] = []
    for idx, app in enumerate(raw_approaches):
        if not isinstance(app, dict) and not isinstance(app, ApproachTelemetry):
            raise TelemetryValidationError(f"Approach at index {idx} must be a dict or ApproachTelemetry.")
        if isinstance(app, ApproachTelemetry):
            approaches.append(app)
        else:
            if not app.get("direction"):
                raise TelemetryValidationError(f"Approach at index {idx} missing 'direction'.")
            approaches.append(ApproachTelemetry.from_dict(app))

    # 3. Build validated JunctionTelemetry
    junction_id = str(payload.get("junction_id", ""))
    if not junction_id:
        raise TelemetryValidationError("Telemetry rejected: missing 'junction_id'.")

    timestamp = payload.get("timestamp") or datetime.now(timezone.utc).isoformat()
    sim_time_s = float(payload["sim_time_s"]) if payload.get("sim_time_s") is not None else None
    current_phase = int(payload.get("current_phase", 0))
    phase_elapsed_s = float(payload.get("phase_elapsed_s", 0.0))
    cycle_length_s = float(payload["cycle_length_s"]) if payload.get("cycle_length_s") is not None else None
    controller = payload.get("controller")
    seed = int(payload["seed"]) if payload.get("seed") is not None else None
    schema_version = str(payload.get("schema_version", "1.0"))

    total_pcu = float(payload.get("total_pcu", 0.0))
    if total_pcu <= 0.0:
        total_pcu = sum(a.pcu for a in approaches)

    return JunctionTelemetry(
        schema_version=schema_version,
        junction_id=junction_id,
        timestamp=timestamp,
        sim_time_s=sim_time_s,
        source=source_enum,
        approaches=approaches,
        current_phase=current_phase,
        phase_elapsed_s=phase_elapsed_s,
        cycle_length_s=cycle_length_s,
        controller=controller,
        total_pcu=total_pcu,
        seed=seed
    )


def resolve_junction_uuid(identifier: str) -> Optional[uuid.UUID]:
    """
    Resolves a string identifier to a UUID if possible, otherwise returns None.
    Used as first stage of junction identity resolution.
    """
    try:
        return uuid.UUID(identifier)
    except (ValueError, TypeError, AttributeError):
        return None
