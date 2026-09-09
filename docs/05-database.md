# 05 — Database Schema & Migrations

Current schema is created by `backend/alembic/versions/001_initial_schema.py`. This roadmap adds migrations `002` … `007`. **Every migration must have a working `downgrade()`** — verified by SN-140.

---

## 1. Existing tables (do not restructure)

| Table | Key columns | Notes |
|---|---|---|
| `users` | `id`, `email` (unique), `password_hash`, `name`, `role`, `is_active` | `role` enum extended in 007 |
| `junctions` | `id`, `name`, `latitude`, `longitude`, `location` (POINT/4326, GiST), `num_approaches`, `geometry` JSON | PostGIS; `location` auto-synced by `@validates` |
| `traffic_sensors` | `id`, `junction_id` FK, `sensor_type`, `approach_direction` | enums `SensorType`, `ApproachDirection` |
| `traffic_readings` | composite PK `(id, timestamp)`, `sensor_id`, `junction_id`, `vehicle_count`, `pcu_value`, `avg_speed`, `queue_length`, `vehicle_breakdown` JSON, `source` | **hypertable**, 7-day chunks |
| `signal_plans` | `id`, `junction_id`, `name`, `phases` JSON, `is_active`, `mode` (`MARL`/`WEBSTER`/`MANUAL`) | mode becomes functional in Phase 2 |
| `alerts` | `id`, `junction_id`, `alert_type`, `severity`, `message`, `is_acknowledged` | |
| `emergency_events` | `id`, `priority`, `vehicle_type`, `route` JSON, `status`, `activated_by`, `started_at`, `ended_at` | extended in 003 |

**SN-008 changes to `traffic_readings`:** `source` becomes `NOT NULL` and constrained to the `DataSource` enum. The existing default `"live"` is meaningless and must be migrated: back-fill existing rows to `'mqtt'` (their actual origin) and drop the default.

---

## 2. Migration 002 — control plane (Phase 2, SN-024)

### `control_decisions`
Every controller action, whether taken or clamped. This table is the evidence that the DQN is real.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `timestamp` | TIMESTAMP PK | hypertable dimension, 1-day chunks |
| `junction_id` | UUID FK → junctions | |
| `controller` | VARCHAR | `marl` \| `webster` \| `manual` |
| `model_version` | VARCHAR | weights file hash; null for webster/manual |
| `state_vector` | JSONB | the 8 values, in order, with names |
| `q_values` | JSONB | null for non-model controllers |
| `action` | SMALLINT | 0 = extend, 1 = advance |
| `action_source` | VARCHAR | `policy` \| `safety_clamp` \| `operator` \| `emergency` |
| `clamped` | BOOLEAN | true if the safety envelope overrode the policy |
| `clamp_reason` | VARCHAR | e.g. `min_green_not_elapsed` |
| `applied_phase` | SMALLINT | |
| `applied_duration_s` | FLOAT | |
| `reward` | FLOAT | computed on the following step |
| `source` | VARCHAR | provenance of the input telemetry |

Indexes: `(junction_id, timestamp DESC)`, `(controller, timestamp DESC)`.

### `ab_runs`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `scenario` | VARCHAR | `normal` \| `surge` \| … |
| `seed` | INTEGER | must be recorded — the number is meaningless without it |
| `duration_s` | INTEGER | |
| `arm_a_controller` | VARCHAR | `webster` |
| `arm_b_controller` | VARCHAR | `marl` |
| `arm_a_metrics` | JSONB | avg_delay, total_delay, avg_queue, avg_wait, throughput, avg_travel_time, vehicles_served |
| `arm_b_metrics` | JSONB | same keys |
| `improvement` | JSONB | per-metric percentage, computed by the documented formula |
| `status` | VARCHAR | `running` \| `complete` \| `failed` |
| `started_at`, `completed_at` | TIMESTAMP | |

**Constraint:** `improvement` is written only when `status = 'complete'` and both arms have identical `seed`, `scenario` and `duration_s`. Enforced in code (SN-038) and asserted by SN-125.

---

## 3. Migration 003 — emergency corridor (Phase 3, SN-040)

Extend `emergency_events`:

| Column | Type | Purpose |
|---|---|---|
| `vehicle_id` | VARCHAR | external identifier |
| `origin_lat`, `origin_lon` | FLOAT | |
| `destination_lat`, `destination_lon` | FLOAT | |
| `destination_name` | VARCHAR | e.g. "District Hospital" |
| `route_etas` | JSONB | `[{junction_id, eta_s, activated_at, passed_at}]` |
| `captured_programs` | JSONB | **real** program logics per junction (replaces `{"mock_plan": true}`) |
| `restored_at` | TIMESTAMP | null until every junction is restored |
| `clearance_time_s` | FLOAT | estimated corridor clearance |
| `cross_street_max_red_s` | FLOAT | measured worst-case conflicting red |
| `recovery_s` | FLOAT | measured time for cross traffic to return to baseline |

**Rule:** `status` may not become `COMPLETED` until `restored_at` is non-null and every entry in `route_etas` has `passed_at` or an explicit timeout reason.

---

## 4. Migration 004 — events & advisories (Phase 4, SN-052, SN-061)

### `events`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `name` | VARCHAR NOT NULL | |
| `event_type` | ENUM | `RALLY`, `PROCESSION`, `FESTIVAL`, `VIP_MOVEMENT`, `MARATHON`, `CONCERT`, `DEMONSTRATION`, `GOVERNMENT`, `OTHER` |
| `starts_at`, `ends_at` | TIMESTAMP NOT NULL | |
| `expected_crowd` | INTEGER | drives the demand translation |
| `affected_links` | JSONB | SUMO edge IDs |
| `closure_links` | JSONB | fully closed edges |
| `intensity` | ENUM | `LOW`, `MEDIUM`, `HIGH` (operator's own estimate, not a prediction) |
| `status` | ENUM | `DRAFT`, `PREDICTED`, `APPROVED`, `PUBLISHED`, `CLOSED`, `CANCELLED` |
| `created_by`, `approved_by` | UUID FK → users | |
| `created_at`, `approved_at`, `published_at` | TIMESTAMP | |

### `event_predictions`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `event_id` | UUID FK | |
| `seed` | INTEGER | must match between both worlds |
| `baseline_metrics` | JSONB | per-link travel time, delay, queue, throughput |
| `event_metrics` | JSONB | same keys, event world |
| `link_deltas` | JSONB | `[{link_id, delta_travel_time_s, delta_pct, severity}]` |
| `severity_summary` | JSONB | counts per severity band |
| `alternatives` | JSONB | ranked routes with added distance/time/congestion/reason |
| `computed_at` | TIMESTAMP | |
| `source` | VARCHAR | always `sumo` — a prediction with any other source is invalid here |

**Severity thresholds** (documented, fixed, not tuned per demo):
`LOW` Δ travel time < 15% · `MODERATE` 15–40% · `SEVERE` > 40%.

### `citizen_advisories`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `origin_type` | ENUM | `EVENT`, `INCIDENT`, `EMERGENCY`, `FORECAST` |
| `origin_id` | UUID | |
| `headline` | VARCHAR(120) | e.g. "Heavy traffic expected: Vijay Nagar → Palasia" |
| `corridor_text` | VARCHAR | human place names only — never junction UUIDs |
| `window_start`, `window_end` | TIMESTAMP | |
| `delay_min_low`, `delay_min_high` | INTEGER | the measured range |
| `cause_text` | VARCHAR | plain language |
| `recommended_route_text` | VARCHAR | |
| `recommended_departure_before` | TIMESTAMP | nullable |
| `severity` | ENUM | `LOW`, `MODERATE`, `SEVERE` |
| `published_by` | UUID FK → users | **non-null — publication is always a human act** |
| `published_at` | TIMESTAMP | |
| `expires_at` | TIMESTAMP | |
| `source` | VARCHAR | provenance of the underlying numbers |

**Constraint:** a row may not exist with `published_by IS NULL`. Advisory publication is a hard human gate (SN-068).

---

## 5. Migration 005 — vision (Phase 5, SN-070)

### `cv_detections` (hypertable, 1-day chunks, **72-hour retention**)
`id` PK, `timestamp` PK, `camera_id`, `track_id`, `vehicle_class`, `confidence`, `bbox` JSONB, `pcu` FLOAT, `frame_ref` VARCHAR (blurred frame path, nullable).

### `behavior_flags`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `flag_type` | ENUM | `WRONG_WAY`, `ILLEGAL_PARKING`, `DANGEROUS_DRIVING` |
| `camera_id`, `track_id` | VARCHAR | |
| `detected_at` | TIMESTAMP | |
| `evidence` | JSONB | motion vectors, lane heading, dwell seconds, jerk values — the measured basis |
| `confidence` | FLOAT | |
| `status` | ENUM | **`UNVERIFIED`** (default), `CONFIRMED`, `DISMISSED` |
| `resolved_by` | UUID FK → users | |
| `resolved_at` | TIMESTAMP | |
| `frame_ref` | VARCHAR | blurred |

**Constraint:** `status` defaults to `UNVERIFIED` and may only change through an operator action that writes an audit row. No automated process may set `CONFIRMED`.

---

## 6. Migration 006 — incidents (Phase 6, SN-084)

### `incidents`
`id` PK, `incident_type` (`POSSIBLE_INCIDENT` only — there is no `ACCIDENT` value by design), `status` (`DETECTED`, `UNVERIFIED`, `UNDER_REVIEW`, `CONFIRMED`, `DISMISSED`, `RESPONDING`, `RESOLVED`, `CLOSED`), `link_id`, `junction_id`, `detected_at`, `confidence`, `indicators_fired` INTEGER, `evidence_ref`, `confirmed_by`, `confirmed_at`, `resolution`, `warning_published_at`, `warning_published_by`.

### `incident_indicators`
`id` PK, `incident_id` FK, `indicator` (`SPEED_COLLAPSE`, `STATIONARY_VEHICLE`, `OCCUPANCY_SPIKE`, `FLOW_DROP`, `QUEUE_ANOMALY`), `measured_value` FLOAT, `threshold` FLOAT, `fired_at` TIMESTAMP.

**Rule:** an incident row must always have at least one indicator row. An incident with no measured indicator is a fabrication and must be rejected at write time.

---

## 7. Migration 007 — governance (Phase 7, SN-098, SN-102)

### `UserRole` enum extension
Add `EMERGENCY_SERVICES`, `CITIZEN`. Postgres enums require `ALTER TYPE ... ADD VALUE`; the downgrade path must recreate the type — document the procedure in the migration itself.

### `audit_logs`
| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `timestamp` | TIMESTAMP PK | hypertable, 30-day chunks, **1-year retention** |
| `actor_type` | ENUM | `USER`, `SYSTEM`, `AI` |
| `actor_id` | UUID | null for `SYSTEM`/`AI` |
| `action` | VARCHAR | e.g. `SIGNAL_OVERRIDE`, `CORRIDOR_ACTIVATE`, `INCIDENT_CONFIRM` |
| `target_type`, `target_id` | VARCHAR / UUID | |
| `input` | JSONB | request payload / model input |
| `output` | JSONB | response / model output |
| `model` | VARCHAR | nullable |
| `model_version` | VARCHAR | nullable |
| `confidence` | FLOAT | nullable — **null unless the actor is a model** |
| `source` | VARCHAR | `DataSource` value |
| `result` | ENUM | `SUCCESS`, `FAILURE`, `DENIED` |
| `correlation_id` | VARCHAR | from `middleware/correlation.py` |

---

## 8. Retention policies (SN-108)

Applied as TimescaleDB retention jobs; verify with `SELECT * FROM timescaledb_information.jobs;`

| Data | Retention | Rationale |
|---|---|---|
| `cv_detections` + raw/blurred frames | **72 hours** | operational need only; minimises personal-data exposure |
| `traffic_readings` (derived counts) | **1 year** | trend analysis; contains no personal data |
| `control_decisions` | 90 days | model behaviour audit |
| `incidents` + `incident_indicators` evidence | **per case** — retained until case closure + 1 year | evidentiary |
| `behavior_flags` | 90 days if `DISMISSED`; per case if `CONFIRMED` | avoids indefinite retention of unverified suspicion |
| `audit_logs` | **1 year** | governance |

---

## 9. Seed data (SN-134)

`scripts/seed_demo.py` creates: 4 junctions matching SUMO `J0..J3` with real Indore-area coordinates and human names; 4 sensors per junction; one user per role; one historic closed event; one resolved incident. **Seeded rows are marked `source='manual'`** so they are never mistaken for measurements.
