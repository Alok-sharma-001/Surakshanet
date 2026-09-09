# 01 — Current State Baseline

**Source of truth:** independent code audit of commit `84f8f6c`, verified against source (not README).
**Overall completion vs. full vision: ~42%.** Vs. the README's own claims: ~65% — that 23-point gap is itself a defect (see SN-147).

Legend for **Current State**:
`REAL` works end-to-end · `PARTIAL` works but path incomplete · `THEATER` presents invented data as output · `MISSING` no code exists

---

## 1. Master index

| # | Subsystem | Current | Target phase | Task IDs |
|---|---|---|---|---|
| 1 | Infrastructure / DevOps | REAL (88%) | 1, 9 | SN-013, SN-018–022, SN-131 |
| 2 | Authentication | REAL | 7 | SN-097, SN-111 |
| 3 | RBAC | PARTIAL (3 roles) | 7 | SN-098–101, SN-112 |
| 4 | Database | REAL | 2–7 | SN-024, SN-040, SN-052, SN-070, SN-084, SN-102 |
| 5 | Telemetry | PARTIAL | 2 | SN-023, SN-025–027 |
| 6 | Redis | REAL | 2 | SN-026, SN-028 |
| 7 | MQTT | REAL | 2 | SN-027 |
| 8 | WebSockets | REAL | 2–6 | SN-029, SN-062, SN-091 |
| 9 | SUMO | REAL (blocked by env) | 1–2 | SN-013–015, SN-030 |
| 10 | TraCI | REAL (not importable in venv) | 1 | **SN-013** |
| 11 | Traffic map | PARTIAL (client-side random) | 2, 5 | SN-005, SN-155 → SN-119 |
| 12 | YOLO detection | PARTIAL (isolated endpoint) | 5 | SN-069–073 |
| 13 | PCU calculation | REAL | 5 | SN-074 |
| 14 | LSTM + XGBoost forecasting | PARTIAL (synthetic-trained) | 0, 2 | SN-006–007, SN-036 |
| 15 | A* routing | PARTIAL (graph not fed live) | 3–4 | SN-041, SN-063–064 |
| 16 | Webster control | PARTIAL (never invoked) | 2 | SN-031, SN-033 |
| 17 | DQN / MARL | **THEATER** (trained, never inferenced) | 2 | **SN-030–038** |
| 18 | Emergency corridor | PARTIAL (mock plan restore) | 3 | SN-039–050 |
| 19 | Frontend | PARTIAL (local fake data) | 0, 2–6 | SN-004–005, SN-119–126 |
| 20 | Training dashboard | **THEATER** (hardcoded metrics) | 0 | **SN-001–003** |
| 21 | CV feed | **THEATER** (`Math.random()` boxes) | 0, 5 | SN-004, SN-078 |
| 22 | Simulation fallback | **THEATER** (`MicroSimRunner` RNG) | 0 | **SN-005** |
| 23 | Accident detection | MISSING | 6 | SN-083–091 |
| 24 | Event / rally management | MISSING (0 files) | 4 | SN-051–060 |
| 25 | Citizen advisory | MISSING (0 files) | 4 | SN-061–068 |
| 26 | Wrong-way detection | MISSING | 5 | SN-075–077 |
| 27 | No-parking detection | MISSING | 5 | SN-079–080 |
| 28 | Rash-driving flagging | MISSING | 5 | SN-081–082 |
| 29 | Drunk-driving handling | MISSING (policy required) | 6 | SN-095–096 |
| 30 | Audit logging | MISSING | 7 | SN-102–106 |
| 31 | Privacy / governance | MISSING | 7 | SN-107–110 |
| 32 | Testing | **THEATER** (tautologies) | 8 | SN-111–126 |
| 33 | Documentation | Overclaims vs. code | 0, 10 | SN-011–012, SN-147 |
| 34 | Data provenance | MISSING | 0, 2 | **SN-008–010** |

---

## 2. Subsystem detail

### 1. Infrastructure / DevOps — `REAL`
- **Current:** `infra/docker-compose.yml` defines `timescaledb`, `redis`, `mosquitto` on network `surakshanet-network`. nginx TLS/HSTS config, Prometheus, Grafana, GitHub Actions, `Makefile` targets, `scripts/{backup_db,purge_history,smoke_check}.sh`. Mosquitto password file mounted (commit `84f8f6c`).
- **Required:** Backend, frontend, SUMO bridge, control service, vision worker and anomaly service all defined and health-checked; single command brings the whole stack up deterministically.
- **Gap:** Compose has infrastructure only — application services are started ad hoc. No orchestrated startup, no per-service health gate.
- **Tasks:** SN-013, SN-018, SN-019, SN-020, SN-021, SN-022, SN-131.
- **Acceptance:** `./start.sh` brings up every service, waits on health checks, prints URLs, and exits non-zero with a named cause if any dependency is unavailable.

### 2. Authentication — `REAL`
- **Current:** JWT HS256, `python-jose`, bcrypt hashing, Redis-backed revocation denylist (`revoke_token` / `is_token_revoked`), login rate limiting (`check_login_rate_limit`, `record_login_failure`), refresh tokens, `seed_default_admin`. Production secret validation in `config.py::validate_production_secrets`.
- **Required:** Unchanged behaviour, plus every login/logout written to the audit log.
- **Gap:** No audit trail on authentication events.
- **Tasks:** SN-097, SN-111.
- **Acceptance:** Integration test proves login success, login failure, rate-limit lockout, token revocation and `/auth/me`; each produces an `audit_logs` row.

### 3. RBAC — `PARTIAL`
- **Current:** `UserRole` = `ADMIN | OPERATOR | VIEWER` (`backend/app/models/user.py:8`). Guard helper `require_role(*roles)` exists at `backend/app/services/auth_service.py:202` but is applied inconsistently — several mutating endpoints use `get_optional_current_user`, i.e. they accept anonymous callers (e.g. `signals.py::update_signal_mode`, `signals.py::override_signal_phase`, `emergency.py::activate_emergency`).
- **Required:** Five roles — `ADMIN`, `OPERATOR`, `EMERGENCY_SERVICES`, `CITIZEN`, `VIEWER`. Every endpoint explicitly bound to a role set via a documented permission matrix. Public citizen endpoints are the only unauthenticated routes.
- **Gap:** Two roles missing; guards not enforced on mutating routes; no permission matrix.
- **Tasks:** SN-098, SN-099, SN-100, SN-101, SN-112.
- **Acceptance:** Permission matrix in [16-rbac.md](16-rbac.md) is fully implemented; a test asserts 403 for every role/endpoint pair marked "deny"; no mutating endpoint accepts an anonymous caller.

### 4. Database — `REAL`
- **Current:** TimescaleDB + PostGIS. Tables: `users`, `junctions`, `traffic_sensors`, `traffic_readings` (hypertable, composite PK `(id, timestamp)`), `signal_plans`, `alerts`, `emergency_events`. One migration: `backend/alembic/versions/001_initial_schema.py`.
- **Required:** Add `events`, `citizen_advisories`, `incidents`, `incident_indicators`, `audit_logs`, `cv_detections`, `behavior_flags`, `control_decisions`, `ab_runs`. Extend `emergency_events` with route ETA and restore state. Retention policies applied per [17-security-privacy.md](17-security-privacy.md).
- **Gap:** Nine tables missing; no retention policy; no audit table.
- **Tasks:** SN-024, SN-040, SN-052, SN-061, SN-070, SN-084, SN-102, SN-108.
- **Acceptance:** `alembic upgrade head` from empty DB creates every table; `alembic downgrade -1` reverses each new migration cleanly; retention policies visible in `timescaledb_information.jobs`.

### 5. Telemetry — `PARTIAL`
- **Current:** `TrafficReading` has a `source` column defaulting to `"live"` — a value that means nothing. `mqtt_consumer.py::_process_telemetry` ingests junction/sensor topics. SUMO bridge publishes to Redis `traffic_updates`.
- **Required:** A single canonical telemetry schema (see [07-telemetry.md](07-telemetry.md)) used identically by SUMO bridge, MQTT consumer and vision worker, with a mandatory `source` enum and per-approach breakdown sufficient to build the 8-dim DQN state.
- **Gap:** No canonical schema; `source` is unconstrained free text; per-approach detail insufficient for state construction.
- **Tasks:** SN-023, SN-025, SN-026, SN-027, SN-008.
- **Acceptance:** All three producers emit schema-valid payloads; a schema-validation test rejects a payload missing `source` or approach data.

### 6. Redis — `REAL`
- **Current:** Pub/sub fanout across workers; channels `traffic_updates`, `signal_events`, `alert_events`, `emergency_events`, `simulation_updates` plus `surakshanet:events:*` aliases (`backend/app/main.py:27`). Also used for the token denylist and login rate limiting.
- **Required:** Add `control_commands`, `control_decisions`, `incident_events`, `event_events`, `advisory_events`, `cv_detections`. Channel list documented and single-sourced.
- **Gap:** New channels not defined; the dual naming scheme (`signal_events` vs `surakshanet:events:signals`) is undocumented drift.
- **Tasks:** SN-026, SN-028.
- **Acceptance:** All channel names come from one constants module; a test asserts every publisher/subscriber pair uses the same constant.

### 7. MQTT — `REAL`
- **Current:** Mosquitto with password auth; consumer subscribes `surakshanet/sensors/+/telemetry` and `surakshanet/junctions/+/telemetry`; topic templates in `shared/constants.py`.
- **Required:** Same, plus conformance to the canonical telemetry schema and `source: "mqtt"` stamping at ingress.
- **Gap:** Ingested payloads are not schema-validated and are not provenance-stamped.
- **Tasks:** SN-027.
- **Acceptance:** A malformed MQTT payload is rejected and logged, not silently written; a valid one lands in `traffic_readings` with `source='mqtt'`.

### 8. WebSockets — `REAL`
- **Current:** `manager.py` with Redis-backed multi-worker fanout; `/ws/{traffic,signals,alerts,emergency,training}` plus `/api/v1/ws`; frontend `websocket.ts` with exponential-backoff reconnect and heartbeat.
- **Required:** Add `/ws/incidents`, `/ws/events`, `/ws/control`. All payloads carry provenance.
- **Gap:** Three channels missing; payload shapes undocumented.
- **Tasks:** SN-029, SN-062, SN-091.
- **Acceptance:** Each channel documented in [06-api-contracts.md](06-api-contracts.md) with an example payload; a test connects and receives a real published message.

### 9. SUMO — `REAL` (blocked by environment)
- **Current:** `/usr/bin/sumo` and `/usr/bin/sumo-gui` installed. Network `simulation/networks/corridor.{nod,edg,net,rou}.xml` — 4 signalised junctions `J0..J3` on a 900 m corridor with N/S side roads, `W_entry`/`E_exit`. `SumoEnvironment` wraps start/step/get_state/set_phase/set_phase_duration/get_metrics.
- **Required:** Deterministic seeded runs; lane-area detectors sufficient for the 8-dim state; two-instance capability for the A/B harness.
- **Gap:** No `--seed` enforcement; no detector definitions; single-instance assumption.
- **Tasks:** SN-014, SN-030, SN-034, SN-127.
- **Acceptance:** Two runs of the same scenario with the same seed produce byte-identical metric series.

### 10. TraCI — `REAL` but **broken in the project venv**
- **Current:** `import traci` succeeds under `/usr/bin/python3`; **fails inside `.venv`** (`ModuleNotFoundError: No module named 'traci'`). `simulation/sumo_env.py` tries `libsumo` then `traci`; `sumo_live_bridge.py` exits with `sys.exit(1)` if neither is importable.
- **Required:** `traci` importable from the same interpreter that runs the backend, the bridge and the control service.
- **Gap:** **This is a guaranteed live-demo failure.** It is the highest-priority environment defect in the project.
- **Tasks:** **SN-013**, SN-016.
- **Acceptance:** `python -c "import traci; print(traci.__file__)"` succeeds inside the venv and inside the backend container; `start.sh` fails loudly with a named cause if it does not.

### 11. Traffic map — `PARTIAL`
- **Current:** Leaflet map renders; `TrafficMapPage.tsx` contains 5 `Math.random()` call sites feeding visible layers.
- **Required:** Every rendered layer sourced from backend state with a provenance badge.
- **Gap:** Client-side invented data.
- **Tasks:** SN-005, SN-119, SN-120.
- **Acceptance:** `grep -rn "Math.random" frontend/dashboard/src/pages/TrafficMapPage.tsx` returns nothing; with the backend stopped the map shows an explicit disconnected state, not moving numbers.

### 12. YOLO detection — `PARTIAL`
- **Current:** `ml/vision/vehicle_detector.py` loads real `yolov8n.pt` (6.5 MB) via `ultralytics`, correct COCO class map (`1 bicycle, 2 car, 3 motorcycle, 5 bus, 7 truck`), graceful fallback when weights absent. Exposed only as `POST /ml/detect` on an uploaded file.
- **Required:** A continuously running vision worker: video → frames → detection → tracking → PCU → canonical telemetry → Redis → control service.
- **Gap:** No frame source, no tracking, no telemetry emission. The model influences nothing.
- **Tasks:** SN-069, SN-070, SN-071, SN-072, SN-073, SN-074.
- **Acceptance:** With the vision worker running on the demo video, `traffic_readings` accumulates rows with `source='vision'` and the CV panel shows those exact detections.

### 13. PCU calculation — `REAL`
- **Current:** `PCU_FACTORS` in `shared/constants.py` (India-appropriate); `ml/vision/pcu_engine.py`; `POST /traffic/pcu` endpoint.
- **Required:** Same factors used identically by vision worker, SUMO bridge and MQTT consumer — one implementation, no duplicates.
- **Gap:** `vehicle_detector.py` carries an inline duplicate fallback table that omits `lcv`.
- **Tasks:** SN-074.
- **Acceptance:** A single PCU function is imported by all three producers; a test asserts identical PCU for identical vehicle mixes across all paths.

### 14. LSTM + XGBoost forecasting — `PARTIAL`
- **Current:** Real ensemble, real trained weights in `ml/forecasting/weights/`. **Trained entirely on `generate_synthetic_data(num_days=14)`** (`train_forecaster.py:60`) — the model has learned its own generator. `GET /ml/predict/{junction_id}` falls back to `sum(ord(c) for c in junction_id) % 15` **stamped `confidence=0.92`** (`api/ml.py:196–214`).
- **Required:** Model predictions returned with `source: "model"`, a declared `training_data: "synthetic"` field and honest confidence. Heuristic fallback returned with `source: "heuristic"` and **no** confidence field, or omitted entirely.
- **Gap:** Fabricated confidence on a string hash; training provenance undeclared.
- **Tasks:** SN-006, SN-007, SN-036.
- **Acceptance:** No response path can emit a `confidence` value for a non-model prediction; a test asserts `source == "heuristic"` implies `confidence is None`.

### 15. A* routing — `PARTIAL`
- **Current:** `ml/routing/routing_engine.py` — genuine A* with haversine distance and congestion-weighted edges (`0.4·travel_time + 0.3·congestion + 0.3·distance`). `POST /routing/route`, `/routing/alternatives`, `GET /routing/congestion`, VMS endpoints. `routing.py:54` contains a hardcoded `"ACCIDENT CLEARED"` VMS string.
- **Required:** Graph built from real junction/edge topology and refreshed from live telemetry on a timer; used by the emergency corridor and the event alternative-route engine.
- **Gap:** `update_edge_weights` is never called with live data; graph is not built from the DB; hardcoded VMS content.
- **Tasks:** SN-041, SN-063, SN-064, SN-010.
- **Acceptance:** Congesting a link in SUMO measurably changes the route returned by `POST /routing/route` within one refresh interval.

### 16. Webster control — `PARTIAL`
- **Current:** `ml/marl/webster_fallback.py` implements Webster's optimal cycle and green splits and can push a `traci.trafficlight.Logic`. Never invoked by any API or service.
- **Required:** The A/B baseline controller, selected by `SignalMode.WEBSTER`, running in the control service.
- **Gap:** No invocation path.
- **Tasks:** SN-031, SN-033.
- **Acceptance:** Setting a junction to `WEBSTER` visibly changes its timing to the Webster plan in SUMO.

### 17. DQN / MARL — `THEATER` — **the project's central defect**
- **Current:** Complete, correct DQN (`agent.py`, `networks.py`, `replay_buffer.py`, `coordinator.py`, `state_dim=8`, `action_dim=2`) with trained weights `ml/marl/weights/marl_policy_downtown.pth` (900 KB). **`grep -rn "MARLCoordinator|MARLAgent" backend/app` returns zero hits — the policy is never loaded for inference.** `PATCH /signals/junctions/{id}/mode` writes an enum and publishes an event that nothing consumes to change control strategy. The "MARL" the dashboard displays is a hardcoded f-string published on a timer: `"MARL Green Extension +4.0s (Junction {id})"` (`simulation/sumo_live_bridge.py:296–307`).
- **Required:** A dedicated control service that loads the policy, subscribes to telemetry, builds the 8-dim state, runs inference, applies the safety envelope, and issues TraCI commands — with every decision logged and published.
- **Gap:** The entire inference and control path.
- **Tasks:** **SN-030 … SN-038**.
- **Acceptance:** A junction in SUMO visibly changes phase behaviour as a direct consequence of DQN inference; `control_decisions` rows show state vector, Q-values, chosen action and any safety clamp; the hardcoded string is deleted.

### 18. Emergency corridor — `PARTIAL`
- **Current:** `POST /emergency/activate` persists an `EmergencyEvent`, publishes to Redis, and the bridge forces green in SUMO. **`GreenWaveController` stores the pre-emption baseline as the literal `{"mock_plan": True}`** (`ml/emergency/green_wave.py:22`) so restoration restores nothing. Default route hardcoded to `["DEL-CP-01","DEL-ITO-02","DEL-ASH-04"]` (`api/emergency.py:38`). All junctions pre-empt simultaneously.
- **Required:** Per-junction ETA, rolling activation, real program capture via `traci.trafficlight.getAllProgramLogics()` and restore, cross-street starvation protection, clearance-time estimate, recovery measurement.
- **Gap:** Four capabilities missing (audit-identified): ETA propagation, real restoration, cross-street protection, clearance estimation.
- **Tasks:** SN-039 … SN-050.
- **Acceptance:** The corridor visibly propagates ahead of the vehicle and reverts behind it; post-corridor cross-street delay returns to within 10% of baseline and the recovery time is displayed.

### 19. Frontend — `PARTIAL`
- **Current:** 20 pages, React 18 + TS, Zustand stores, error boundaries, reconnecting WS. But `hooks/useTrafficSimulationEngine.ts` generates telemetry **in the browser** from templated event strings, and 7 components run `Math.random()` loops. `components/Studio/Studio3DSphere.tsx` alone has 10.
- **Required:** Frontend renders backend state only. Provenance badges everywhere. Studio/3D frozen.
- **Gap:** Client-side data fabrication; no provenance display.
- **Tasks:** SN-004, SN-005, SN-009, SN-119 … SN-126.
- **Acceptance:** With the backend stopped, no page displays moving traffic numbers; every numeric panel shows a provenance badge.

### 20. Training dashboard — `THEATER` — **highest immediate risk**
- **Current:** `backend/app/api/ml.py:88` initialises `_training_status = {"episode": 420, "current_reward": 14.2, "avg_reward_100": 11.8, "best_reward": 22.4, "epsilon": 0.05, ...}`. `run_marl_training_task` sleeps 0.5 s per tick and computes `current_reward = 10.0 + ep*0.4 + ep%3`. **No gradient step occurs.** A learning curve is drawn from arithmetic.
- **Required:** Either a real training runner writing real episode metrics, or an endpoint that reports `status: "unavailable"` with a reason.
- **Gap:** Fabricated model metrics served from a production API.
- **Tasks:** **SN-001, SN-002, SN-003**.
- **Acceptance:** `grep -n "420\|14.2\|11.8\|22.4" backend/app/api/ml.py` returns nothing; the training endpoint either reflects a real run or returns `unavailable`.

### 21. CV feed — `THEATER`
- **Current:** `ComputerVisionFeed.tsx:26–46` — five hardcoded boxes labelled `CAR/BUS/BIKE/PEDESTRIAN` at 91–98% confidence, drifting via `Math.random()` every 400 ms, with `fps = 29.8 + Math.random()*0.8`.
- **Required:** Render actual detections from the vision worker, with real confidence and real frame rate; explicit "no video source" state otherwise.
- **Gap:** A fake version of a capability the project genuinely has.
- **Tasks:** SN-004, SN-078.
- **Acceptance:** Every box drawn corresponds to a detection record received from the backend; stopping the worker shows "no video source", not moving boxes.

### 22. Simulation fallback — `THEATER`
- **Current:** `backend/app/api/simulation.py:22–70` — `MicroSimRunner` produces vehicles/speed/delay/queue from `random.randint` and `random.uniform`, presented through the same response shape as real SUMO output. Selected whenever SUMO/TraCI is unreachable.
- **Required:** Delete. When SUMO is unavailable the API returns `503` with `{"status": "simulation_unavailable", "reason": ...}`.
- **Gap:** RNG labelled as simulation.
- **Tasks:** **SN-005**.
- **Acceptance:** Class removed; with SUMO stopped, `GET /simulation/state` returns the unavailable payload and the UI shows "Simulation unavailable".

### 23. Accident detection — `MISSING`
- **Current:** Only UI strings (`LiveIncidents.tsx:26`, `AIInsightsTicker.tsx:31`, `Navbar.tsx:121`). No detector of any kind.
- **Required:** Multi-indicator anomaly detection (speed collapse, stationary vehicle outside queue, occupancy spike, flow drop downstream, queue anomaly) producing `Possible incident` with indicator list, confidence and `UNVERIFIED` status — never a crash classification.
- **Gap:** Entire subsystem.
- **Tasks:** SN-083 … SN-091.
- **Acceptance:** Blocking a lane in SUMO raises an incident within 60 s listing which indicators fired; no code path emits the word "accident" as a determination.

### 24. Event / rally management — `MISSING`
- **Current:** Keyword sweep across `backend/app`, `ml`, `frontend/dashboard/src` for `rally`, `event_management`, `special event` returns **0 files**.
- **Required:** `Event` entity, operator creation UI, dual-world SUMO what-if, severity classification, ranked alternative routes, approval → advisory publication.
- **Gap:** Entire subsystem.
- **Tasks:** SN-051 … SN-060.
- **Acceptance:** Creating an event and running the what-if produces measured per-link deltas from two SUMO runs, and approval emits a citizen advisory.

### 25. Citizen advisory — `MISSING`
- **Current:** Keyword sweep for `citizen`, `public_alert` returns **0 files**. No public route; no `CITIZEN` role.
- **Required:** Unauthenticated public route answering where/why/how bad/how long/what to do in under three seconds, fed by the event, incident, emergency and prediction subsystems.
- **Gap:** Entire subsystem.
- **Tasks:** SN-061 … SN-068.
- **Acceptance:** An operator approving a diversion causes a public advisory to appear at `/public` within 5 s without a login.

### 26. Wrong-way detection — `MISSING`
- **Current:** No code.
- **Required:** Tracking-based comparison of motion vector against lane heading, alerting only after sustained opposition; output `UNVERIFIED`.
- **Gap:** Entire subsystem. Identified by the audit as the highest-ROI real CV feature.
- **Tasks:** SN-075, SN-076, SN-077.
- **Acceptance:** A wrong-way vehicle in the demo video/SUMO raises exactly one flag with track evidence; normal traffic raises none over a full scenario run.

### 27. No-parking detection — `MISSING`
- **Current:** No code (`parking` → 0 files).
- **Required:** Operator-drawn restricted polygon + stationary dwell timer → `possible illegal parking` with duration, class and snapshot. ANPR off by default.
- **Gap:** Entire subsystem.
- **Tasks:** SN-079, SN-080.
- **Acceptance:** A vehicle stationary in a restricted polygon beyond threshold produces one flag; a vehicle queued at a red signal produces none.

### 28. Rash-driving flagging — `MISSING`
- **Current:** No code.
- **Required:** Kinematic proxies (speed, lane-change rate, lateral jerk, headway) producing `Dangerous driving behaviour flagged for review` — never a violation determination.
- **Gap:** Entire subsystem.
- **Tasks:** SN-081, SN-082.
- **Acceptance:** Flags exist only in `UNVERIFIED` state until an operator resolves them; no string in the codebase asserts guilt or a confirmed violation.

### 29. Drunk-driving handling — `MISSING` (policy artefact required)
- **Current:** No code, no policy statement.
- **Required:** An explicit documented prohibition plus the correct workflow: AI behaviour flag → patrol alert → officer verification → breathalyser → confirmed case.
- **Gap:** The policy must be documented and enforced by a test.
- **Tasks:** SN-095, SN-096.
- **Acceptance:** A test greps the whole repository and fails if any file claims camera-based intoxication detection; the workflow appears in the UI and in [22-hackathon-demo.md](22-hackathon-demo.md).

### 30. Audit logging — `MISSING`
- **Current:** No audit table, no logging of operator or AI decisions.
- **Required:** `audit_logs` capturing actor, timestamp, action, input, output, model, model version, confidence, source, result — for every override, corridor activation, incident confirm/dismiss, public warning, event approval, diversion and AI decision.
- **Gap:** Entire subsystem.
- **Tasks:** SN-102 … SN-106.
- **Acceptance:** Each of the nine listed action types writes exactly one audit row; a test asserts the row's required fields are non-null.

### 31. Privacy / governance — `MISSING`
- **Current:** Infrastructure security is done (TLS, JWT revocation, broker auth, secret validation). Data governance is absent.
- **Required:** Blur-by-default on faces/plates, ANPR disabled in demo, retention policy (raw frames 72 h, derived counts 1 y, incident evidence per case), documented model limitations, false-positive workflow.
- **Gap:** Entire data-governance layer.
- **Tasks:** SN-107 … SN-110.
- **Acceptance:** Stored/served frames are blurred; a config flag gates ANPR and defaults off; retention jobs exist and are verifiable.

### 32. Testing — `THEATER`
- **Current:** 443 assertions across ~5,700 lines; **104 assert only that a file exists**. `tests/e2e/tier3_combinations/test_cross_feature_combinations.py:194` asserts `len("rrrrGGGggrrrrGGGgg") == 18` — a tautology over a literal defined two lines above. API tests assert `status_code in (200, 401)`, which passes whether auth works or is completely broken.
- **Required:** 15 real critical-path integration tests that fail when behaviour breaks. Decorative tests deleted, not supplemented.
- **Gap:** Effective coverage ≈ 25%.
- **Tasks:** SN-111 … SN-126.
- **Acceptance:** Every one of the 15 paths in [19-testing.md](19-testing.md) has a test that fails when the corresponding feature is deliberately broken (mutation check required).

### 33. Documentation — overclaims
- **Current:** `README.md` describes MARL signal control and green-wave dispatch as operating capabilities. `STATUS.md`, `ROADMAP.md`, `TEST_READY.md` similarly overstate. Gap vs. code ≈ 23 points.
- **Required:** Documentation states only what is implemented, integrated, tested and demonstrable; simulated vs. production clearly separated.
- **Gap:** Truth pass over all root-level docs.
- **Tasks:** SN-011, SN-012, SN-147.
- **Acceptance:** Every capability claim in `README.md` maps to a passing test ID and a demo scenario; reviewer confirms no aspirational feature is described in present tense.

### 34. Data provenance — `MISSING`
- **Current:** `TrafficReading.source` defaults to the meaningless `"live"`. No provenance in API responses or the UI.
- **Required:** Mandatory `source` enum on every value; distinct UI treatment per source; heuristic values visually and structurally distinguishable from measured/model values.
- **Gap:** Entire contract.
- **Tasks:** **SN-008, SN-009, SN-010**.
- **Acceptance:** A response-schema test asserts `source` present on every telemetry/prediction/metric payload; a UI test asserts heuristic values render with the heuristic badge and never with the model badge.
