# 07 — Telemetry & Data Provenance

Covers **SN-008, SN-023, SN-025 … SN-028**. This document defines the one schema every producer emits and the provenance contract that makes the rest of the system defensible.

---

## 1. Why this exists

Today `TrafficReading.source` defaults to `"live"` — a value that distinguishes nothing. Three producers (SUMO bridge, MQTT consumer, and the future vision worker) emit differently-shaped payloads, and the API returns numbers without saying where they came from. The audit's rule R2 requires that **every value declares its origin**, because the difference between a measurement and an estimate is the difference between an engineering project and a demo.

---

## 2. The `DataSource` enum (SN-008)

Add to `shared/constants.py`:

```python
class DataSource(str, enum.Enum):
    SUMO      = "sumo"       # measured from the microsimulation via TraCI
    VISION    = "vision"     # derived from camera frames by the detector
    MQTT      = "mqtt"       # reported by a physical/simulated edge device
    MODEL     = "model"      # produced by a trained model (forecaster, DQN)
    HEURISTIC = "heuristic"  # produced by a formula, NOT a trained model
    MANUAL    = "manual"     # entered or seeded by a human
```

**Semantics that must not be blurred:**

| Source | Is it measured? | May carry `confidence`? | UI treatment |
|---|---|---|---|
| `sumo` | yes (from simulation) | no | measured badge |
| `vision` | yes (from frames) | yes — the detector's own confidence | measured badge + per-detection confidence |
| `mqtt` | yes (from device) | no | measured badge |
| `model` | no — inferred | **yes, and only here for predictions** | model badge |
| `heuristic` | no — computed from a rule | **never** | heuristic badge, visually distinct |
| `manual` | no — asserted | no | manual badge |

The rule that resolves the audit's worst finding: **`confidence` may not accompany `heuristic`.** `GET /ml/predict/{id}` currently returns a forecast derived from `sum(ord(c) for c in junction_id) % 15` stamped `confidence=0.92`. After SN-006 that path returns `source: "heuristic"` and no confidence field at all.

---

## 3. Canonical telemetry schema (SN-023)

New module `shared/telemetry.py`. All three producers import and emit this; the control service and anomaly service consume only this.

```python
@dataclass
class ApproachTelemetry:
    direction: str            # "N" | "E" | "S" | "W"  (matches ApproachDirection)
    lane_ids: list[str]
    vehicle_count: float
    pcu: float                # via shared PCU function (SN-074)
    queue_length_m: float
    mean_speed_kmh: float
    occupancy: float          # 0.0 - 1.0
    accumulated_wait_s: float
    vehicle_breakdown: dict[str, int]   # class -> count

@dataclass
class JunctionTelemetry:
    schema_version: str = "1.0"
    junction_id: str                    # SUMO tl id or DB UUID (see §5)
    timestamp: str                      # ISO-8601 UTC
    sim_time_s: float | None            # populated when source == sumo
    source: DataSource                  # MANDATORY
    approaches: list[ApproachTelemetry]
    current_phase: int
    phase_elapsed_s: float
    cycle_length_s: float | None
    controller: str | None              # "marl" | "webster" | "manual" | None
    total_pcu: float                    # sum over approaches
    seed: int | None                    # populated when source == sumo
```

**Validation (SN-027):** a payload missing `source`, missing `approaches`, or carrying an unknown `source` value is **rejected and logged** — never partially written. Test SN-114 asserts rejection.

---

## 4. Producers

### SUMO bridge (SN-025) — `simulation/sumo_live_bridge.py`
Reads per-approach values from the lane-area detectors defined in SN-015 (`det_{junction}_{direction}_{lane}`). Emits `source=SUMO` with `sim_time_s` and `seed` populated. Publish rate: 2 Hz default, configurable, must be ≥ the control step rate.

Also deleted here: the hardcoded `"MARL Green Extension +4.0s"` publisher at lines 296–307 (SN-002). The bridge reports state; it does not narrate decisions.

### MQTT consumer (SN-027) — `backend/app/services/mqtt_consumer.py`
Topics unchanged (`surakshanet/junctions/+/telemetry`, `surakshanet/sensors/+/telemetry`). Validates against the schema, stamps `source=MQTT` at ingress, rejects malformed payloads with a logged reason.

### Vision worker (SN-072) — `services/vision_worker/main.py`
Aggregates tracked detections over the detection window into approach-level counts and PCU, emits `source=VISION`. Per-detection confidences are carried in `cv_detections`, not in the aggregate telemetry.

**Interchangeability requirement (Gate 5):** the control service must consume SUMO and vision telemetry without code changes. Only `source` differs.

---

## 5. Identity mapping

SUMO uses string traffic-light IDs (`J0`…`J3`); the database uses UUIDs. Resolution rules:

1. The seed script (SN-134) creates junctions whose `name` matches the SUMO id exactly.
2. `shared/telemetry.py` exposes `resolve_junction(identifier) -> UUID | None` using the existing pattern in `backend/app/api/signals.py::_resolve_junction_uuid` (UUID parse, then `name ILIKE`).
3. Telemetry carries the **producer's native id**; resolution happens once, at the persistence boundary.
4. An unresolvable id is logged and the reading is dropped — **never** written against a placeholder junction.

---

## 6. Redis channels (SN-026, SN-028)

Single source in `shared/constants.py`:

```python
REDIS_CHANNELS = {
    "traffic":            "traffic_updates",
    "signals":            "signal_events",
    "alerts":             "alert_events",
    "emergency":          "emergency_events",
    "simulation":         "simulation_updates",
    "control_commands":   "control_commands",     # NEW: control service → bridge
    "control_decisions":  "control_decisions",    # NEW: control service → API/UI
    "incidents":          "incident_events",      # NEW
    "events":             "event_events",         # NEW
    "advisories":         "advisory_events",      # NEW
    "cv_detections":      "cv_detections",        # NEW
}
```

**SN-028 also removes existing drift:** `backend/app/main.py:27` subscribes to both `signal_events` and `surakshanet:events:signals`. Pick one scheme (the short names), delete the alias set, and make every publisher and subscriber read from `REDIS_CHANNELS`. A test asserts no literal channel string appears outside this constant.

---

## 7. Persistence

`traffic_readings.source` becomes `NOT NULL` with an enum constraint (SN-008). Existing rows back-fill to `'mqtt'`. Write path: telemetry → validate → resolve junction → PCU via the shared function → insert. Write rate is throttled to one row per junction per second; the full-rate stream stays on Redis for the control loop, which needs latency, not history.

---

## 8. Provenance in responses and UI (SN-009)

**API:** every telemetry, prediction, metric and decision payload carries `source`. Enforced by a shared Pydantic base model so it cannot be forgotten.

**UI:** extend the existing `frontend/dashboard/src/components/TelemetrySourceBadge.tsx` to render all six sources with distinct treatment. Requirements:

- Measured sources (`sumo`, `vision`, `mqtt`) share one visual family.
- `model` is visually distinct from measured.
- **`heuristic` is visually distinct from both**, and its value is rendered with an explicit qualifier (e.g. "estimated") — never in the same typographic style as a measured number (R3).
- `manual` is distinct and used for seeded/entered data.
- A panel with no source cannot render a number at all; it renders the unavailable state.

**Test SN-123** asserts: every numeric panel has a badge; a heuristic value never renders with the model badge; and no component displays a number when `source` is absent.
