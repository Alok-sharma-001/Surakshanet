# 03 — Development Roadmap: Phases 0–10

Each phase specifies **Goal · Tasks · Dependencies · Files affected · APIs · DB changes · UI changes · Tests · Acceptance criteria · Demo validation · Completion gate**.

**Phase gates are hard.** Do not begin phase *N+1* until phase *N*'s completion gate passes. Task detail lives in [`CHECKLIST.md`](CHECKLIST.md).

Effort figures assume one focused developer; a team of three can parallelise phases 4/5 against 2/3 after Phase 2 lands.

---

## PHASE 0 — Cleanup (credibility & integrity)

> The audit identifies fabricated presentation as the single biggest immediate risk. Nothing else in this roadmap matters if a judge finds an invented number first. **This phase is deletion-heavy and must complete before any feature work.**

**Goal:** No fabricated value can reach an API response or the UI. Every value carries provenance. Documentation stops overclaiming.

**Tasks:** SN-001 … SN-012 (≈ 1.5 days)

| ID | Task |
|---|---|
| SN-001 | Delete hardcoded `_training_status` seed values and the fake `run_marl_training_task` reward arithmetic in `backend/app/api/ml.py:88–125`. |
| SN-002 | Delete the hardcoded `"MARL Green Extension +4.0s"` publisher in `simulation/sumo_live_bridge.py:296–307`. |
| SN-003 | Rebuild `GET /ml/train/status` to report a real run or `{"status":"unavailable","reason":...}`. |
| SN-004 | Replace `ComputerVisionFeed.tsx` random boxes/FPS with real detections or a "no video source" state. |
| SN-005 | Delete `MicroSimRunner` (`backend/app/api/simulation.py:22–70`); return `503 simulation_unavailable`. |
| SN-006 | Remove `confidence` from heuristic forecast responses (`api/ml.py:196–214`); stamp `source: "heuristic"`. |
| SN-007 | Declare `training_data: "synthetic"` on all forecaster model responses. |
| SN-008 | Add `DataSource` enum + mandatory `source` field to `shared/constants.py` and all response schemas. |
| SN-009 | Frontend: provenance badge component; heuristic values visually distinct from model/measured. |
| SN-010 | Remove hardcoded VMS content (`api/routing.py:54`, `RoutingPage.tsx:43`). |
| SN-011 | Rewrite `README.md` to describe only implemented behaviour. |
| SN-012 | Reconcile `STATUS.md`, `ROADMAP.md`, `TEST_READY.md`, `TEST_INFRA.md` with actual code state. |

**Dependencies:** none. This is the entry point.

**Files affected:** `backend/app/api/{ml,simulation,routing}.py`; `simulation/sumo_live_bridge.py`; `shared/constants.py`; `backend/app/schemas/{ml,traffic}.py`; `frontend/dashboard/src/components/CommandCenter/ComputerVisionFeed.tsx`; `frontend/dashboard/src/pages/{RoutingPage,SimulationPage,TrafficMapPage}.tsx`; `frontend/dashboard/src/components/TelemetrySourceBadge.tsx`; `README.md`, `STATUS.md`, `ROADMAP.md`, `TEST_READY.md`, `TEST_INFRA.md`.

**APIs:** `GET /ml/train/status` semantics changed (real or unavailable). `GET /ml/predict/{id}` gains `source`, loses `confidence` on heuristic path. `GET /simulation/state` returns 503 when SUMO is down. All telemetry/prediction responses gain `source`.

**DB changes:** none.

**UI changes:** provenance badge on every numeric panel; "Simulation unavailable" state; "No video source" state; training panel shows real state or unavailable.

**Tests:** SN-123 (provenance contract) is written here in stub form and completed in Phase 8. Immediate greps are part of acceptance.

**Acceptance criteria:**
1. `grep -rn "Math.random" frontend/dashboard/src --include=*.tsx | grep -v Studio/` returns **no** result in a data-bearing component.
2. `grep -n "420\|14\.2\|11\.8\|22\.4" backend/app/api/ml.py` returns nothing.
3. `grep -rn "MicroSimRunner" backend/` returns nothing.
4. No response schema permits `confidence` when `source != "model"`.
5. Every claim in `README.md` maps to code that exists.

**Demo validation:** with the backend stopped, open every page — no page displays moving traffic numbers.

**COMPLETION GATE 0:** A reviewer greps the repository for the four patterns above and finds nothing; the README truth-pass is signed off. *No feature work begins until this passes.*

---

## PHASE 1 — Infrastructure & demo reliability

> The audit identifies `traci` missing from the project venv as a guaranteed live-demo failure. Fix the environment before building on it.

**Goal:** Any machine can bring the entire stack up with one command, deterministically, with a clear failure message when a dependency is missing.

**Tasks:** SN-013 … SN-022 (≈ 1 day)

| ID | Task |
|---|---|
| SN-013 | **Fix `traci` in the venv.** Install `eclipse-sumo`/`traci` into `.venv` (or recreate with `--system-site-packages`); pin in `requirements.txt`. |
| SN-014 | Enforce `--seed` on every SUMO invocation from `shared/constants.py::DEMO_SEED`. |
| SN-015 | Add lane-area detectors to `simulation/networks/` sufficient for the 8-dim state. |
| SN-016 | Startup import guard: backend, bridge and control service fail loudly if `traci` is unimportable. |
| SN-017 | `requirements.txt` / `requirements-dev.txt` pinned and reproducible. |
| SN-018 | Write `start.sh` (10-step contract, below). |
| SN-019 | `/health` and `/health/deep` endpoints reporting each dependency. |
| SN-020 | Per-service health checks in `infra/docker-compose.demo.yml`. |
| SN-021 | `stop.sh` and `reset.sh` (reset restores seeded demo state). |
| SN-022 | Document exact versions in [04-environment-setup.md](04-environment-setup.md). |

**Dependencies:** Phase 0 complete.

**Files affected:** `start.sh`, `stop.sh`, `reset.sh` (new, repo root); `requirements.txt`; `infra/docker-compose.demo.yml` (new); `backend/app/main.py` (health routes); `simulation/networks/corridor.det.xml` (new); `simulation/sumo_env.py`; `shared/constants.py`.

**APIs:** `GET /health` → `{"status":"ok"}`; `GET /health/deep` → per-dependency status for postgres, redis, mqtt, sumo, traci, control_service, vision_worker, model weights.

**DB changes:** none.

**UI changes:** header shows live system health from `/health/deep`.

**Tests:** SN-126 (startup smoke) — `start.sh` from a cold machine reaches all-green.

**Acceptance criteria:**
1. `source .venv/bin/activate && python -c "import traci"` succeeds.
2. `./start.sh` performs: dependency check → infra start → health wait → backend → SUMO bridge → control service → frontend → verification → URL print, and returns 0.
3. With Redis stopped, `./start.sh` exits non-zero naming Redis as the cause within 60 s.
4. Two runs of the same scenario at the same seed produce identical metric series.

**Demo validation:** cold-boot the machine, run `./start.sh`, reach a working dashboard without manual steps.

**COMPLETION GATE 1:** `./start.sh` succeeds three consecutive times from a clean state; `/health/deep` reports all dependencies healthy.

---

## PHASE 2 — Real AI control (highest engineering priority)

> The audit's central finding: the intelligence layer is disconnected from the control layer. This phase connects them and produces the project's headline evidence.

**Goal:** A live SUMO junction visibly changes signal behaviour because of actual DQN inference, and the improvement over fixed-time is measured, not asserted.

**Tasks:** SN-023 … SN-038 (≈ 3 days)

| ID | Task |
|---|---|
| SN-023 | Canonical telemetry schema in `shared/telemetry.py`. |
| SN-024 | Migration: `control_decisions`, `ab_runs` tables. |
| SN-025 | SUMO bridge emits canonical telemetry incl. per-approach detail. |
| SN-026 | `REDIS_CHANNELS` constants; add `control_commands`, `control_decisions`. |
| SN-027 | MQTT consumer validates schema and stamps `source="mqtt"`. |
| SN-028 | Single-source all channel names; remove naming drift. |
| SN-029 | `/ws/control` WebSocket channel. |
| SN-030 | **Control service skeleton**: lifecycle, config, model loading, Redis subscribe. |
| SN-031 | Controller strategies: `MarlController`, `WebsterController`, `ManualController`. |
| SN-032 | **Safety envelope** module — hard clamp applied to every action. |
| SN-033 | Mode routing: `SignalMode` from DB drives strategy selection. |
| SN-034 | State builder: telemetry → 8-dim vector, exactly matching training. |
| SN-035 | Reward computation and persistence of every decision. |
| SN-036 | Forecaster integration with honest provenance. |
| SN-037 | Prometheus metrics for the control loop. |
| SN-038 | **A/B runner**: two SUMO instances, same seed, Webster vs DQN, measured deltas. |

**Dependencies:** Phase 1 (traci, seeds, detectors).

**Files affected:** `services/control_service/{main,controllers,safety,state,reward,config}.py` (new); `services/control_service/ab_runner.py` (new); `shared/telemetry.py`, `shared/constants.py`; `simulation/sumo_live_bridge.py`; `backend/app/api/{signals,ml,simulation}.py`; `backend/app/models/control.py` (new); `backend/alembic/versions/002_*.py` (new); `frontend/.../pages/SignalControlPage.tsx`, `SimulationPage.tsx`; new `ABComparisonPanel.tsx`.

**APIs:**
- `GET /signals/junctions/{id}/decision` — latest control decision incl. state vector, Q-values, action, safety clamp, reason.
- `POST /ab/run` — start an A/B comparison for a scenario+seed.
- `GET /ab/runs/{run_id}` — live and final metrics for both arms.
- `PATCH /signals/junctions/{id}/mode` — now actually changes controller behaviour.

**DB changes:** `control_decisions` (junction, ts, state vector, q_values, action, clamped, reason, controller, model_version, reward); `ab_runs` (run_id, scenario, seed, arm metrics, improvement_pct, computed_at).

**UI changes:** signal panel shows current phase, controller mode, AI decision + reason, remaining green, queue, wait — all live. New A/B split-screen panel with two live metric series and a computed improvement figure.

**Tests:** SN-116 (DQN inference), SN-117 (safety envelope), SN-115 (SUMO telemetry), SN-125 (A/B determinism).

**Acceptance criteria:**
1. Switching a junction to `MARL` changes its phase behaviour in SUMO; switching to `WEBSTER` restores fixed-time timing.
2. Every decision writes a `control_decisions` row containing the state vector and the chosen action.
3. A crafted state that would produce a 2-second green is clamped to `min_green_s` and the clamp is recorded.
4. The A/B improvement percentage is computed by a documented formula from SUMO output; changing the seed changes the number.
5. `grep -rn "MARL Green Extension" .` returns nothing.

**Demo validation:** Scenario B — surge on one approach; the agent visibly extends that approach's green while the A/B panel shows the delay gap widening.

**COMPLETION GATE 2:** A reviewer sets a junction to MARL, watches SUMO, and reads the corresponding `control_decisions` row for the phase change they just observed.

---

## PHASE 3 — Emergency green corridor

**Goal:** The corridor propagates ahead of the vehicle on predicted arrival, restores the real prior program behind it, and its cost to cross traffic is measured and shown.

**Tasks:** SN-039 … SN-050 (≈ 1.5 days)

| ID | Task |
|---|---|
| SN-039 | `EmergencyVehicle` model + extend `emergency_events` (route, ETAs, restore state, clearance). |
| SN-040 | Migration for the above. |
| SN-041 | Feed the A* graph from live telemetry on a refresh timer. |
| SN-042 | Per-junction ETA calculation from live link speeds. |
| SN-043 | Rolling activation scheduler (pre-empt at `ETA − clearance`, not all at once). |
| SN-044 | **Capture real program** via `traci.trafficlight.getAllProgramLogics()`; replace `{"mock_plan": True}`. |
| SN-045 | Restore captured program on pass-through; verify restoration. |
| SN-046 | Cross-street starvation guard (compensating phase above threshold). |
| SN-047 | Clearance-time estimate + live countdown. |
| SN-048 | Recovery measurement after corridor close. |
| SN-049 | Remove hardcoded default route `["DEL-CP-01",...]`. |
| SN-050 | Emergency dashboard panel (vehicle, ETA, route, activated junctions, next junction, countdown, cross-traffic impact, recovery). |

**Dependencies:** Phase 2 (control service owns signal authority; corridor pre-empts through it).

**Files affected:** `ml/emergency/green_wave.py`; `backend/app/api/emergency.py`; `backend/app/models/alert.py`; `services/control_service/` (pre-emption hook); `ml/routing/routing_engine.py`; `frontend/.../pages/EmergencyPage.tsx`; `backend/alembic/versions/003_*.py`.

**APIs:** `POST /emergency/activate` (real route required), `GET /emergency/{id}/eta`, `GET /emergency/{id}/corridor`, `POST /emergency/{id}/position`, `GET /emergency/{id}/recovery`, `POST /emergency/deactivate/{id}`.

**DB changes:** `emergency_events` + `route_etas JSONB`, `captured_programs JSONB`, `clearance_time_s`, `recovery_s`, `cross_street_max_red_s`.

**UI changes:** map corridor propagation (green ahead, reverted behind), per-junction ETA labels, countdown, recovery chart.

**Tests:** SN-118 (corridor lifecycle incl. restoration and recovery).

**Acceptance criteria:**
1. Junctions turn green in ETA order, not simultaneously.
2. After pass-through, `getAllProgramLogics()` matches the captured pre-corridor program.
3. No conflicting approach exceeds the configured max red during a corridor.
4. Recovery time is measured from telemetry and displayed.
5. `grep -rn "mock_plan" ml/` returns nothing.

**Demo validation:** Scenario C — corridor visibly travels with the ambulance; recovery chart appears after it clears.

**COMPLETION GATE 3:** A reviewer runs Scenario C twice at the same seed and gets the same ETA sequence and the same recovery figure.

---

## PHASE 4 — Event / rally management + citizen advisory

> Built together because the citizen advisory is the output of the event pipeline. The audit identifies these two as the project's clearest differentiators; both are currently 0 files.

**Goal:** An operator creates an event, runs a measured what-if, approves a diversion, and a citizen sees the advisory — with no invented numbers anywhere in that chain.

**Tasks:** SN-051 … SN-068 (≈ 2.5 days)

| ID | Task |
|---|---|
| SN-051 | `Event` model + enums. |
| SN-052 | Migration: `events`. |
| SN-053 | Event CRUD API with RBAC. |
| SN-054 | Demand translation: crowd size → additional trips (documented mode-split assumptions). |
| SN-055 | **Dual-world what-if runner** (baseline vs event, identical seed). |
| SN-056 | Per-link delta computation + severity classification thresholds. |
| SN-057 | Alternative route ranking via A*. |
| SN-058 | Approval workflow (`DRAFT → PREDICTED → APPROVED → PUBLISHED → CLOSED`). |
| SN-059 | Event dashboard page (create, select roads, run prediction, compare, approve, publish). |
| SN-060 | Event → advisory generation hook. |
| SN-061 | `CitizenAdvisory` model + migration. |
| SN-062 | Public API `GET /public/advisories` (+ `/public/status`), no auth, rate-limited. |
| SN-063 | Advisory content builder (where/why/how bad/how long/what to do). |
| SN-064 | Departure-time recommendation from the forecast horizon. |
| SN-065 | Public route `/public` in React Router, outside the auth layout. |
| SN-066 | Citizen view UI — 3-second read, no technical clutter. |
| SN-067 | Wire incident + emergency + prediction sources into advisories. |
| SN-068 | Advisory publication is a **human gate** (operator approval required) and is audited. |

**Dependencies:** Phase 2 (SUMO harness reuse), Phase 3 (emergency source), Phase 1 (determinism).

**Files affected:** `backend/app/models/event.py`, `advisory.py` (new); `backend/app/api/events.py`, `public.py` (new); `backend/app/api/router.py`; `services/control_service/ab_runner.py` (reused for dual-world); `ml/routing/routing_engine.py`; `frontend/.../pages/EventsPage.tsx`, `PublicAdvisoryPage.tsx` (new); `App.tsx`; `backend/alembic/versions/004_*.py`.

**APIs:** `POST/GET/PATCH /events`, `POST /events/{id}/predict`, `GET /events/{id}/prediction`, `POST /events/{id}/approve`, `POST /events/{id}/publish`, `GET /public/advisories`, `GET /public/advisories/{id}`, `GET /public/status`.

**DB changes:** `events`, `event_predictions`, `citizen_advisories`.

**UI changes:** operator Events page; separate unauthenticated `/public` page with its own minimal layout (not the dashboard chrome).

**Tests:** SN-119 (dual-world what-if), SN-120 (advisory generation), SN-113 (public endpoint requires no auth but exposes no protected data).

**Acceptance criteria:**
1. The what-if runs two SUMO simulations and reports per-link travel-time deltas; no severity is assigned without measured data.
2. Alternative routes come from A* on live-weighted edges, each with added distance, added time, congestion level and reason.
3. Approving a diversion creates an advisory visible at `/public` within 5 s.
4. `/public` returns no junction IDs, no model internals, no operator data.
5. An unapproved event never produces a public advisory.

**Demo validation:** Scenario D — schedule tomorrow's rally, run prediction, approve, cut to the phone view.

**COMPLETION GATE 4:** Operator action → citizen advisory demonstrated end-to-end, with the advisory's numbers traceable to the what-if run that produced them.

---

## PHASE 5 — Computer vision pipeline

**Goal:** The CV panel shows real inference; vision becomes an interchangeable telemetry source alongside SUMO; the highest-ROI behavioural detector (wrong-way) ships.

**Tasks:** SN-069 … SN-082 (≈ 2 days)

| ID | Task |
|---|---|
| SN-069 | Vision worker skeleton: video/RTSP source, frame loop, configurable detection interval. |
| SN-070 | Migration: `cv_detections`, `behavior_flags`. |
| SN-071 | Detection → tracking (IoU/centroid tracker with stable track IDs). |
| SN-072 | Track → class → PCU → canonical telemetry publish (`source="vision"`). |
| SN-073 | Failure behaviour: no source / decode error → explicit unavailable, never synthetic. |
| SN-074 | Single PCU implementation shared by all producers; remove the duplicate table in `vehicle_detector.py`. |
| SN-075 | Lane geometry + heading configuration per camera. |
| SN-076 | **Wrong-way detector**: sustained motion opposed to lane heading. |
| SN-077 | Wrong-way flag persistence + `UNVERIFIED` status + operator resolve. |
| SN-078 | CV panel renders real detections, real confidence, real FPS. |
| SN-079 | Restricted-polygon editor + `no_parking_zones` config. |
| SN-080 | **No-parking detector**: stationary dwell timer inside polygon, queue-aware. |
| SN-081 | **Rash-driving proxies**: speed, lane-change rate, lateral jerk, headway. |
| SN-082 | Behaviour flags are review-only; language audit forbids guilt/violation phrasing. |

**Dependencies:** Phase 2 (telemetry schema + control service consuming it), Phase 0 (fake CV feed removed).

**Files affected:** `services/vision_worker/{main,tracker,wrongway,parking,behavior,config}.py` (new); `ml/vision/{vehicle_detector,pcu_engine,rtsp_stream_worker}.py`; `backend/app/api/vision.py` (new); `backend/app/models/vision.py` (new); `frontend/.../components/CommandCenter/ComputerVisionFeed.tsx`; `backend/alembic/versions/005_*.py`.

**APIs:** `GET /vision/detections/latest`, `GET /vision/status`, `GET /vision/flags`, `PATCH /vision/flags/{id}/resolve`, `POST /vision/zones`, `GET /vision/zones`.

**DB changes:** `cv_detections` (ts, camera, track_id, class, confidence, bbox, pcu); `behavior_flags` (type, camera, track_id, evidence, confidence, status, resolved_by, resolved_at).

**UI changes:** CV panel with real boxes and a "no video source" state; flags list with UNVERIFIED badge and resolve/dismiss actions; zone editor.

**Tests:** SN-121 (vision → telemetry), SN-122 (wrong-way true/false positive).

**Acceptance criteria:**
1. Running the worker on the demo video writes `traffic_readings` rows with `source='vision'`.
2. Every box in the UI corresponds to a `cv_detections` record.
3. A wrong-way vehicle raises exactly one flag with track evidence; a full normal-traffic run raises zero.
4. A vehicle queued at red does not raise a no-parking flag.
5. No string in the repository asserts a confirmed violation from vision alone (enforced by SN-082's grep test).

**Demo validation:** show the CV panel with real detections, then stop the worker and show the honest unavailable state.

**COMPLETION GATE 5:** Vision and SUMO are interchangeable telemetry sources — the control service consumes both without code changes.

---

## PHASE 6 — Incident detection & response

**Goal:** Multi-indicator anomaly detection producing reviewable `Possible incident` records, driving a state machine with explicit human gates.

**Tasks:** SN-083 … SN-096 (≈ 1.5 days)

| ID | Task |
|---|---|
| SN-083 | `Incident` + `IncidentIndicator` models. |
| SN-084 | Migration: `incidents`, `incident_indicators`. |
| SN-085 | Anomaly service skeleton subscribing to `traffic_updates`. |
| SN-086 | Indicator 1: sudden speed reduction on a link. |
| SN-087 | Indicator 2: stationary vehicle outside a signal queue. |
| SN-088 | Indicator 3: occupancy spike; Indicator 4: downstream flow drop; Indicator 5: queue anomaly. |
| SN-089 | Combination rule + confidence from indicator count/strength (documented, not tuned to look good). |
| SN-090 | Incident creation with `UNVERIFIED` status, evidence snapshot reference. |
| SN-091 | `/ws/incidents` + incident API. |
| SN-092 | Operator actions: confirm / dismiss / escalate (human gate). |
| SN-093 | Post-confirmation automation: reroute + dispatch (assisted). |
| SN-094 | Public warning publication — **second human gate**, audited. |
| SN-095 | **Drunk-driving policy artefact**: documented prohibition + correct workflow. |
| SN-096 | Repo-wide language test forbidding intoxication-detection claims. |

**Dependencies:** Phase 5 (evidence snapshots), Phase 4 (advisory channel for public warnings), Phase 2 (telemetry).

**Files affected:** `services/anomaly_service/{main,indicators,rules}.py` (new); `backend/app/models/incident.py`, `backend/app/api/incidents.py` (new); `frontend/.../pages/AlertsPage.tsx`, `components/CommandCenter/LiveIncidents.tsx`; `backend/alembic/versions/006_*.py`.

**APIs:** `GET /incidents`, `GET /incidents/{id}`, `POST /incidents/{id}/confirm`, `POST /incidents/{id}/dismiss`, `POST /incidents/{id}/escalate`, `POST /incidents/{id}/publish-warning`.

**DB changes:** `incidents` (type, status, location, ts, confidence, indicators_fired, evidence_ref, confirmed_by, confirmed_at, resolution); `incident_indicators` (incident_id, indicator, value, threshold, fired_at).

**UI changes:** incident cards showing which indicators fired and their values; UNVERIFIED badge; confirm/dismiss/escalate controls; publish-warning button distinctly marked as irreversible.

**Tests:** SN-122 (incident lifecycle with human gate).

**Acceptance criteria:**
1. Blocking a lane in SUMO raises an incident within 60 s listing the indicators that fired with their measured values.
2. No rerouting or public warning occurs before operator confirmation.
3. The UI never renders the word "accident" as a determination — only "possible incident".
4. `pytest tests/test_language_policy.py` fails if any file claims camera-based intoxication detection.

**Demo validation:** Scenario E, including the honesty beat ("it says *possible*, because a camera can flag an anomaly — it cannot certify a crash").

**COMPLETION GATE 6:** The full detected → confirmed → responded → warned → resolved path runs, with both human gates demonstrably blocking automation until a person acts.

---

## PHASE 7 — Governance: RBAC, audit, privacy

**Goal:** Five roles enforced everywhere, every consequential action audited, privacy defaults defensible.

**Tasks:** SN-097 … SN-110 (≈ 1 day)

| ID | Task |
|---|---|
| SN-097 | Audit login/logout/token events. |
| SN-098 | Add `EMERGENCY_SERVICES` and `CITIZEN` to `UserRole` + migration. |
| SN-099 | Implement the full permission matrix from [16-rbac.md](16-rbac.md). |
| SN-100 | Replace `get_optional_current_user` on all mutating endpoints with `require_role(...)`. |
| SN-101 | Restrict corridor activation to `EMERGENCY_SERVICES`/`ADMIN`; rate-limit overrides. |
| SN-102 | `AuditLog` model + migration. |
| SN-103 | Audit middleware/helper writing actor, ts, action, input, output, model, model_version, confidence, source, result. |
| SN-104 | Wire audit into all nine mandatory action types. |
| SN-105 | Audit for AI decisions (control decisions, incident creation, advisory generation). |
| SN-106 | Audit viewer page (ADMIN only). |
| SN-107 | Blur-by-default on stored/served frames. |
| SN-108 | Retention policies: raw frames 72 h, derived counts 1 y, incident evidence per case. |
| SN-109 | ANPR config flag, default off, documented. |
| SN-110 | Model-limitations document + false-positive tracking. |

**Dependencies:** Phases 2–6 (the actions to be audited must exist).

**Files affected:** `backend/app/models/{user,audit}.py`; `backend/app/services/audit_service.py` (new); every `backend/app/api/*.py`; `services/vision_worker/privacy.py` (new); `scripts/retention.sh` (new); `frontend/.../pages/AuditPage.tsx` (new); `backend/alembic/versions/007_*.py`.

**APIs:** `GET /audit` (ADMIN), `GET /audit/{id}`; all existing endpoints gain enforced role guards.

**DB changes:** `audit_logs`; `UserRole` enum extension; TimescaleDB retention jobs.

**UI changes:** audit viewer; role-aware navigation (menu items hidden AND routes guarded).

**Tests:** SN-112 (RBAC matrix), SN-124 (audit completeness), SN-113 (public exposure).

**Acceptance criteria:**
1. Every role/endpoint pair marked "deny" returns 403.
2. Each of the nine mandatory action types writes exactly one complete audit row.
3. Faces/plates are blurred in any stored or served frame; ANPR flag defaults off.
4. Retention jobs are visible in `timescaledb_information.jobs`.

**Demo validation:** show the audit trail for the corridor activation and the incident confirmation performed earlier in the demo.

**COMPLETION GATE 7:** A reviewer picks any three actions performed during a demo run and finds a complete audit row for each.

---

## PHASE 8 — Testing rebuild

**Goal:** Replace decorative tests with tests that fail when behaviour breaks.

**Tasks:** SN-111 … SN-126 (≈ 1 day)

| ID | Task |
|---|---|
| SN-111 | Auth critical path. |
| SN-112 | RBAC matrix. |
| SN-113 | Public advisory permissions/exposure. |
| SN-114 | Telemetry ingestion (MQTT + schema rejection). |
| SN-115 | SUMO telemetry determinism. |
| SN-116 | DQN inference produces a real, reproducible action. |
| SN-117 | Safety envelope clamps an unsafe action. |
| SN-118 | Emergency corridor lifecycle incl. restoration. |
| SN-119 | Event dual-world what-if. |
| SN-120 | Citizen advisory generation. |
| SN-121 | Vision → telemetry. |
| SN-122 | Incident confirmation gate + wrong-way detection. |
| SN-123 | Provenance contract. |
| SN-124 | Audit logging completeness. |
| SN-125 | A/B reproducibility. |
| SN-126 | Service startup smoke. |

**Dependencies:** all preceding phases.

**Files affected:** delete `tests/e2e/tier1_features/`, `tier2_*`, `tier3_combinations/` tautologies; create `tests/critical/test_{01..15}_*.py`; `Makefile` test targets; CI workflow.

**Acceptance criteria:**
1. Each of the 15 paths has a test that **fails when the corresponding feature is deliberately broken** (mutation check documented in the test's docstring).
2. `grep -rn "assert len(\"" tests/` returns nothing.
3. No test asserts `status_code in (200, 401)`.
4. Test count may decrease; effective coverage must not.

**Demo validation:** `make test-critical` runs green in under 5 minutes.

**COMPLETION GATE 8:** For three randomly chosen tests, deliberately breaking the feature makes the test fail.

---

## PHASE 9 — Demo hardening

**Goal:** The demo is deterministic, rehearsed, and survives a hostile network.

**Tasks:** SN-127 … SN-138 (≈ 1 day)

| ID | Task |
|---|---|
| SN-127 | Fixed seed enforced across all five scenarios. |
| SN-128 | Scenario A (normal) config + verification. |
| SN-129 | Scenario B (surge). |
| SN-130 | Scenario C (ambulance). |
| SN-131 | Scenario D (rally). |
| SN-132 | Scenario E (incident). |
| SN-133 | Scenario switcher in the UI. |
| SN-134 | Seeded demo dataset (junctions, users, one historic event). |
| SN-135 | Demo run-book with exact click sequence and timings. |
| SN-136 | **Record backup video** of a full clean run. |
| SN-137 | Failure drill: rehearse the demo with the network unplugged. |
| SN-138 | Judge Q&A preparation from [22-hackathon-demo.md](22-hackathon-demo.md). |

**Acceptance criteria:**
1. Each scenario produces identical numbers across runs at the same seed.
2. All scenario outputs are measured; no scripted text presents a number.
3. The recorded backup covers all seven demo beats.
4. `./reset.sh && ./start.sh` returns to a known demo state in under 3 minutes.

**COMPLETION GATE 9:** Three consecutive full rehearsals with identical measured outputs and no manual intervention.

---

## PHASE 10 — Final acceptance

**Goal:** Prove, item by item, that nothing from the audit or the original vision is unresolved.

**Tasks:** SN-139 … SN-150 (≈ 0.5 day)

| ID | Task |
|---|---|
| SN-139 | Complete the 5-condition matrix in [23-final-acceptance.md](23-final-acceptance.md). |
| SN-140 | Verify every Phase 0 deletion still holds (regression grep). |
| SN-141 | Verify the end-to-end chain (13 stages) in one run. |
| SN-142 | Re-verify determinism after all changes. |
| SN-143 | Confirm every audit finding has a resolving task marked DONE. |
| SN-144 | Confirm every original-vision requirement is addressed or explicitly declined with reason. |
| SN-145 | Performance sanity: control loop latency, API p95, WS fanout. |
| SN-146 | Full-chain integration demonstration recorded. |
| SN-147 | Final documentation truth pass. |
| SN-148 | Verify no forbidden feature was added (3D, ANPR-on, drunk-driving claims). |
| SN-149 | Compute and publish final completion percentage from the checklist. |
| SN-150 | Sign-off. |

**Acceptance criteria:** No row in the final matrix is marked complete unless **Implemented ∧ Integrated ∧ Tested ∧ Demonstrated ∧ Documented** are all true.

**COMPLETION GATE 10:** The final matrix has zero incomplete rows, or each incomplete row carries a written, accepted justification.

---

## Effort summary

| Phase | Days (1 dev) | Cumulative | Unlocks |
|---|---|---|---|
| 0 Cleanup | 1.5 | 1.5 | Credibility floor |
| 1 Infrastructure | 1.0 | 2.5 | Demo can run at all |
| 2 Real AI control | 3.0 | 5.5 | **The headline claim + evidence** |
| 3 Emergency corridor | 1.5 | 7.0 | Strongest emotional beat |
| 4 Event + citizen | 2.5 | 9.5 | **Differentiation** |
| 5 Computer vision | 2.0 | 11.5 | Honest CV + wrong-way |
| 6 Incident system | 1.5 | 13.0 | Response story |
| 7 Governance | 1.0 | 14.0 | Wins the hard questions |
| 8 Testing | 1.0 | 15.0 | Survives source inspection |
| 9 Demo hardening | 1.0 | 16.0 | Survives the stage |
| 10 Final acceptance | 0.5 | 16.5 | Sign-off |

**Minimum viable path if time is short:** Phases 0 → 1 → 2 → 3 → 9 (≈ 8 days) reaches finalist-level. Phase 4 is what makes the winner argument; do not drop it before Phase 5 or 6.
