# CLAUDE.md — Surakshanet ITS: Persistent Operating Instructions

> This file is the **persistent source of project knowledge** for Claude Code sessions.
> Before broad codebase exploration, always check this file and `git status`/`git diff` first.
> Every claim in this file has been verified against the code as of 2026-09-10 (Phases 0, 1,
> and 2 closed — see §1). Trust it, but if a specific fact matters for a risky change, `grep`
> to confirm — this file records what was true when last checked, not a live view.
> Update this file when discovering stable architectural knowledge or important design
> constraints. Never let it re-accumulate unverified claims — see §21.

---

## 1. Project Identity & Current Status

**Surakshanet** is an Intelligent Transportation System (ITS) for urban traffic monitoring,
spatial junction management, adaptive signal optimization, and operator observability. It
is undergoing a **10-phase hardening effort** driven by an independent code audit. The
execution surface is `docs/CHECKLIST.md` (SN-001…SN-150, grouped into Phases 0–10); the
`docs/NN-*.md` files are the specification each phase implements against.

**Status, verified 2026-09-10:**
- **Phase 0 (Cleanup, SN-001…SN-012k):** DONE. Closed on branch `phase0/complete`. A
  CI-blocking regression guard (`scripts/check_phase0_regressions.sh`, `make check-phase0`,
  26 checks) enforces that fabricated-data patterns cannot silently return.
- **Phase 1 (Infrastructure, SN-013…SN-022):** DONE. `docs/25-phase1-remediation-plan.md`
  documents the 10 defects found in review and their fixes — all implemented and covered by
  the guard above.
- **Phase 2 (Real AI control, SN-012f + SN-023…SN-038):** DONE. Remediation plan
  (`docs/26-phase2-remediation-plan.md`) executed to 100% completion:
  - Local `.venv` dependencies (`torch`, `sqlalchemy`, `pydantic`, etc.) installed.
  - All 24 critical tests in `tests/critical/` pass with zero errors.
  - MARL training rebuilt against real SUMO with lane-area detectors (SN-012f); policy weights
    `ml/marl/weights/marl_policy_downtown.pth` trained and verified (SHA-256: `c3b9cb12...`).
  - Pre-audit fabricated benchmark files purged and docs sanitized.
  - TraCI duration semantics and safety envelope ped cycles fixed in `ab_runner.py`; live 900s
    A/B evaluation executed via `POST /ab/run` and persisted to TimescaleDB table `ab_runs`
    (run `8646126e-da0b-4602-ae0c-fdd8e0b2af3b`, Webster: 726.84s delay vs MARL: 826.32s delay,
    honest delta reporting).
  - All SN items (SN-012f, SN-023…SN-038) individually verified; `docs/CHECKLIST.md` reconciled
    to 17/17 DONE (total progress: 48/161 DONE, 30%).
- **Phases 3–10:** NOT_STARTED.
**Pre-audit benchmark cleanup:** The fabricated pre-audit benchmark files (`ml/benchmarks/results/baseline_study_*.{md,json}`) have been deleted, and references in `docs/RESEARCH_DEFENSE.md` and `STATUS.md` purged per `docs/26-phase2-remediation-plan.md` item 6. Real benchmark results are produced live by `services/control_service/ab_runner.py` and stored in the `ab_runs` database table.

---

## 2. Repository Layout

```
surakshanet/
├── backend/             # FastAPI application (Python 3.11)
│   ├── app/
│   │   ├── api/         # Route handlers — includes health.py, ab.py, simulation.py
│   │   ├── config.py    # Pydantic Settings (reads .env)
│   │   ├── database.py  # SQLAlchemy async engine + advisory-lock-guarded Alembic runner
│   │   ├── main.py      # FastAPI app factory, lifespan, middleware, traci hard-guard
│   │   ├── middleware/  # CorrelationId, Prometheus metrics (incl. control_* series)
│   │   ├── models/      # SQLAlchemy ORM — includes models/control.py (ControlDecision, ABRun)
│   │   ├── schemas/     # Pydantic v2 request/response schemas
│   │   ├── services/    # auth, traffic_service, mqtt_consumer
│   │   └── websocket/   # ConnectionManager (manager.py); /ws/control added Phase 2
│   ├── alembic/versions/  # 001_initial_schema, 001b_datasource_provenance, 002_control_decisions_ab_runs
│   ├── tests/           # 11 pytest files, asyncio_mode = auto
│   └── requirements.txt # Pinned; torch, sqlalchemy installed in .venv (see §11)
├── frontend/dashboard/  # React 18 + TypeScript + Vite SPA (18 route-level pages)
├── ml/
│   ├── marl/            # DQN agent, webster_fallback.py; train_marl.py drives real SumoEnvironment (SN-012f)
│   ├── vision/           # YOLOv8 detector; raises VisionUnavailable rather than fabricating (shared/exceptions.py)
│   ├── forecasting/      # LSTM forecaster, lazy-loaded, trained on synthetic data (declared honestly)
│   ├── emergency/         # Green-wave preemption (green_wave.py)
│   ├── routing/
│   └── benchmarks/results/  # Purged; real results produced live by ab_runner.py in ab_runs DB table
├── simulation/
│   ├── sumo_env.py          # TraCI wrapper. Raises catchable ImportError (not SystemExit) on missing traci —
│   │                         # its callers (api/simulation.py, ml/marl/train_marl.py) rely on except ImportError
│   ├── sumo_live_bridge.py  # Live bridge — FRAGILE, 20KB. Emits canonical JunctionTelemetry (SN-025) via REDIS_CHANNELS
│   └── networks/            # corridor.{net,edg,nod,rou,det,sumocfg}.xml — 4 junctions, DEMO_SEED=42
├── services/control_service/  # SN-030: controllers.py, safety.py, state.py, reward.py, ab_runner.py, config.py, main.py
├── shared/
│   ├── constants.py     # DataSource enum, PCU_FACTORS, REDIS_CHANNELS, DEMO_SEED=42, SIGNAL_CONSTRAINTS
│   ├── telemetry.py     # ApproachTelemetry / JunctionTelemetry canonical schema (SN-023)
│   ├── sumo_bootstrap.py # ensure_sumo_on_path() + require_traci() — the ONE place the traci-guard lives (§13.11)
│   ├── paths.py          # find_existing() / resolve_repo_path() — the ONE place candidate-path search lives
│   ├── schemas.py
│   └── exceptions.py     # VisionUnavailable
├── infra/                # docker-compose.yml (dev), docker-compose.demo.yml, docker-compose.prod.yml
├── scripts/
│   ├── check_phase0_regressions.sh  # 26 checks, CI-blocking (`phase0-guard` job), covers Phase 0 AND Phase 1 findings
│   └── smoke_check.sh               # checks /health for "healthy" (not "ok" — see §13.3)
├── tests/
│   ├── e2e/              # Opaque-box E2E suite, Tiers 1-4
│   └── critical/         # Phase 2 mutation-checked tests (SN-116/125 etc) — see §11, currently only partially runnable locally
├── docs/                 # 00-26 + CHECKLIST.md; 25 and 26 are the Phase 1/2 remediation plans
├── start.sh / stop.sh / reset.sh  # SN-018/021 orchestration; start.sh writes /health/deep to a temp file, never splices JSON into Python source
├── .env.example
├── Makefile
└── .github/workflows/    # ci.yml (phase0-guard + backend + frontend jobs), deploy.yml
```

---

## 3. Technology Stack

### Backend
| Layer | Technology |
|---|---|
| Framework | FastAPI 0.104.1 (async) |
| Python | 3.11 (repo pins this; **note**: `.venv` currently runs 3.14 with missing deps — see §11) |
| ORM | SQLAlchemy 2.0 (async/asyncpg), classic `Column[]` style, not `Mapped[]` |
| DB Driver | asyncpg (PostgreSQL), aiosqlite (test fallback) |
| Migrations | Alembic 1.13 — advisory-lock-guarded against concurrent-worker races (§13.11) |
| Spatial | GeoAlchemy2 + PostGIS (`Geometry('POINT', srid=4326)`) |
| Time-series | TimescaleDB hypertables (`traffic_readings`, `control_decisions`) |
| Auth | JWT (HS256) via `python-jose`, bcrypt via `passlib`, `jti` Redis revocation |
| Messaging | Redis pub/sub (redis-py asyncio), paho-mqtt |
| ML | PyTorch, Ultralytics YOLOv8, XGBoost, scikit-learn — all lazy-loaded, never at module import |
| Simulation | Eclipse SUMO + TraCI (`traci>=1.19`, `eclipse-sumo>=1.19`, pinned in requirements.txt) |
| Metrics | Prometheus (`prometheus-client`), includes `control_*` series (SN-037) |
| Validation | Pydantic v2 + pydantic-settings |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript, `React.lazy()` code splitting per page |
| Build | Vite 5, tsc strict mode |
| Routing | react-router-dom v6 |
| State | Zustand 4 |
| HTTP | axios |
| Maps | Leaflet + react-leaflet, mapbox-gl |
| Charts | Recharts |
| 3D | Three.js (decorative `Studio/` components only — excluded from the fabrication guard) |
| Styling | Tailwind CSS 3, light theme |
| Testing | Vitest + React Testing Library + jsdom |

### Infrastructure
| Service | Image | Host Port | Compose file |
|---|---|---|---|
| TimescaleDB + PostGIS | `timescale/timescaledb-ha:pg15` | 5432/5433 | dev / demo |
| Redis | `redis:7-alpine` | 6379 (127.0.0.1 only) | both |
| Mosquitto MQTT | `eclipse-mosquitto:2` | 1883 (127.0.0.1 only) | both — healthcheck has NO `\|\| exit 0` escape (fixed Phase 1) |
| FastAPI Backend | custom Dockerfile, `--workers 2` | 8000 | demo |
| Prometheus | official | 9090 | demo |
| Grafana | official | 3001 (demo) / 3000 (prod) | demo/prod |

---

## 4. Database Schema

### Key Tables
**`users`** — `id` UUID PK, `email` unique, `role` enum `ADMIN|OPERATOR|VIEWER`. Registration
always creates `OPERATOR`; admin promotion is an explicit separate action, never self-service.

**`junctions`** — spatial master. `location` `Geometry('POINT', srid=4326)` auto-synced from
`latitude`/`longitude` via `Junction.__init__` and `@validates` — always update both together.

**`traffic_sensors`** — `sensor_type: CAMERA|INDUCTION|ACOUSTIC|GPS`, FK to `junctions.id`
(CASCADE DELETE).

**`traffic_readings`** — TimescaleDB hypertable. Composite PK `(id, timestamp)` — required by
the hypertable, never change to a single PK. `source` column has a CHECK constraint against
the `DataSource` enum (`sumo|vision|mqtt|model|heuristic|manual`) — NOT NULL, no default of
`"live"` (that was removed in migration `001b`). `avg_speed` and `queue_length` are nullable —
an unreported value is `NULL`, never a fabricated default.

**`control_decisions`** (new, SN-024) — TimescaleDB hypertable, 1-day chunks. Records every
control-service decision: `state_vector`, `clamped`/`clamp_reason`, `reward` (filled one step
later), `controller` (marl/webster/manual).

**`ab_runs`** (new, SN-024) — one row per A/B comparison run (`services/control_service/
ab_runner.py`). `improvement` is absent until the run genuinely completes — never filled with
a placeholder.

**`alerts`**, **`emergency_events`** — see `docs/05-database.md` for full field lists.

### Alembic
Three migrations: `001_initial_schema`, `001b_datasource_provenance`,
`002_control_decisions_ab_runs`. `database.py::init_db()` runs migrations under a Postgres
advisory lock (`pg_try_advisory_lock`) so `--workers 2` booting concurrently don't race each
other into a spurious failure — a genuine migration failure now propagates and crashes
startup rather than being logged and swallowed (fixed in Phase 1; see §13.12).

---

## 5. API Architecture

### REST Endpoints (all under `/api/v1`)
| Router | File | Key Endpoints |
|---|---|---|
| `/auth` | `api/auth.py` | `POST /register` (always OPERATOR), `POST /login`, `POST /logout` |
| `/users` | `api/users.py` | `PATCH /{user_id}/role` (ADMIN only) |
| `/traffic` | `api/traffic.py` | Readings CRUD; rejects (422) a reading missing NOT NULL fields or an unattributable junction rather than defaulting |
| `/junctions` | `api/junctions.py` | Spatial queries |
| `/ml` | `api/ml.py` | `POST /ml/detect` (YOLOv8, 503 if weights absent), `/ml/predict` (503 if no readings and no trained model) |
| `/simulation` | `api/simulation.py` | SUMO TraCI control; 503 `simulation_unavailable` when SUMO absent — no fabricated fallback |
| `/ab` | `api/ab.py` | (new, SN-038) A/B comparison runs |
| `/routing` | `api/routing.py` | A* pathfinding |
| `/alerts` | `api/alerts.py` | Alert CRUD |
| `/emergency` | `api/emergency.py` | `POST /activate` — 422 if no route supplied, never assumes a corridor |
| `/signals` | `api/signals.py` | Signal plan management; `mode` field now actually consumed by the control service (SN-033) |
| `/health` | `api/health.py` | `GET /health` liveness → `{"status": "healthy"}`; `GET /health/deep` readiness → per-dependency `ok`/`degraded`/`error`/`unavailable`, never assumed |
| `/metrics` | `main.py` | Prometheus scrape (no prefix) |

### WebSocket Endpoints (no `/api/v1` prefix)
```
/ws/traffic /ws/signals /ws/alerts /ws/emergency /ws/training /ws/control (new)
/ws/{channel}  (dynamic)   /api/v1/ws  (channel: 'default')
```
`app/websocket/manager.py::ConnectionManager`. Cross-worker broadcast via Redis pub/sub;
`redis_pubsub_bridge()` in `main.py` dispatches to local clients via `manager.local_broadcast()`.

---

## 6. Authentication & Security
- JWT HS256 via `python-jose`; `jti` claim enables individual revocation via Redis key
  `revoked_token:{jti}`, checked on every request in `get_current_user()`.
- Login lockout after 5 failures, tracked in Redis (`auth:failed_logins:{email}`).
- RBAC: `ADMIN|OPERATOR|VIEWER`. Registration always creates `OPERATOR` — never trust a role in
  the request body.
- `config.py::validate_production_secrets()` blocks startup under `ENVIRONMENT=production` with
  a default `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, or dev DB credentials.
- CORS: `sanitize_cors_origins` strips any `*` origin.
- No credential defaults live in test fixtures — `tests/e2e/conftest.py`'s `admin_token`
  fixture skips (does not fall back to a hardcoded password) when `ADMIN_EMAIL`/
  `ADMIN_PASSWORD` aren't set in the environment.

---

## 7. Data Provenance Contract (MANDATORY)

Every telemetry payload, WebSocket frame, and `traffic_readings.source` value MUST carry a
`DataSource` (`shared/constants.py`):

| Enum Value | String | Meaning |
|---|---|---|
| `DataSource.SUMO` | `"sumo"` | Measured from SUMO microsimulation via TraCI |
| `DataSource.VISION` | `"vision"` | Vehicle *counts* from the YOLOv8 detector — NOT speed or queue length, which a single frame cannot measure (both are `null` on vision-sourced rows) |
| `DataSource.MQTT` | `"mqtt"` | Reported by a physical/simulated edge device |
| `DataSource.MODEL` | `"model"` | Produced by a trained model (LSTM forecaster, DQN) — `confidence` is schema-forbidden on any other source |
| `DataSource.HEURISTIC` | `"heuristic"` | Produced by a formula (persistence baseline, Webster), NOT a trained model |
| `DataSource.MANUAL` | `"manual"` | Entered or seeded by a human |

The legacy `live`/`sim`/`mock` vocabulary is retired — it does not satisfy the `traffic_readings.source`
CHECK constraint and must not appear in new code. (It still appears in the contaminated
`STATUS.md`/`docs/RESEARCH_DEFENSE.md` — see §1; do not copy from those files.)

`<TelemetrySourceBadge>` (frontend) has no default prop — a missing or unrecognised source
renders `UNAVAILABLE`, never falls back to a measured-family badge.

**NEVER fabricate, hardcode, or fake data values in API responses, tests, or UI components.**
`scripts/check_phase0_regressions.sh` (26 checks, CI-blocking as the `phase0-guard` job)
enforces this — extend it, don't work around it, when adding new provenance-bearing code.

---

## 8. ML & Simulation Subsystems

### MARL (Multi-Agent Reinforcement Learning)
- `ml/marl/` — DQN agent (`agent.py`), Webster fallback (`webster_fallback.py`)
- **`ml/marl/train_marl.py` trains against real SUMO (SN-012f, verified).** Drives `SumoEnvironment`
  reading the 16 lane-area detectors (`det_{junction}_{dir}_0`), seeds runs deterministically, and
  outputs genuine policy weights `ml/marl/weights/marl_policy_downtown.pth` with SHA-256 verified in
  `tests/critical/test_06_dqn_inference.py`.
- `ml/benchmarks/results/` pre-audit debris was purged. Real numbers are derived live from `ab_runs`.
- Corridor: 4 junctions (J0-J3), an arterial + cross-street topology (`simulation/networks/
  corridor.{nod,edg}.xml`). Phase-string length is topology-dependent — verify against the
  actual `corridor.net.xml` before assuming a specific character count; don't hardcode one from
  memory.

### SUMO / TraCI
- `simulation/sumo_env.py` — TraCI wrapper. Raises a catchable `ImportError` (not `SystemExit`)
  when `traci` is missing, because its callers (`backend/app/api/simulation.py`,
  `ml/marl/train_marl.py`) both implement `except ImportError: SumoEnvironment = None` and
  degrade to an honest 503/skip. Do not change this to `SystemExit` — see §13.11.
- `simulation/sumo_live_bridge.py` — FRAGILE, 20KB, inspect carefully before modifying. Uses
  `require_traci()` from `shared/sumo_bootstrap.py` (hard-exit on missing traci — this file IS
  meant to crash loudly, unlike `sumo_env.py`). Emits canonical `JunctionTelemetry` via
  `REDIS_CHANNELS["traffic"]` (SN-025).
- No fallback engine. When SUMO/TraCI is unreachable, `/simulation/*` returns `503
  {"status":"simulation_unavailable","reason":...}` — never fabricated vehicle/speed/delay data.
  (The old `MicroSimRunner` that did exactly that was deleted in Phase 0, SN-005 — if you see it
  referenced anywhere, that reference is stale.)
- 16 lane-area detectors (`simulation/networks/corridor.det.xml`) — loaded via `corridor.sumocfg`
  for the standalone bridge, and via `additional_files` (resolved through `shared/paths.py`) for
  the REST-driven `/simulation/start` path (Phase 1 fix — previously only the bridge loaded them).

### Control Service (`services/control_service/`, Phase 2)
- `controllers.py` — `MarlController` (SHA-256-verifies weights, refuses MARL mode with a
  `RuntimeError` rather than fabricating a decision if weights fail to load), `WebsterController`,
  `ManualController`.
- `safety.py` — the safety envelope: min/max green, mandatory amber/all-red, pedestrian-service
  guarantee. Every clamp is recorded with a reason.
- `state.py` — builds the ordered 8-dim state vector from `JunctionTelemetry`.
- `reward.py` — computed one control step after the action, never online during a demo.
- `ab_runner.py` — SN-038. Runs two real TraCI simulations (Webster vs MARL), computes honest
  improvement percentages, explicitly reports a negative result unchanged if that's what happens
  (`generate_ab_statement`). **Has not yet actually been executed** — see §1 and the Phase 2 plan.
- `tests/critical/` carries mutation-checked tests for this subsystem (SN-116/117/125). Currently
  only 3 of 5 files fully collect/pass in `.venv` — the gap is missing `torch`/`sqlalchemy`, not a
  code defect. See §11.

### YOLOv8 Vision
- `ml/vision/vehicle_detector.py` — raises `shared.exceptions.VisionUnavailable` (not a fabricated
  detection) when no model is loaded or inference fails. `POST /ml/detect` maps this to `503`.
- `ml/vision/rtsp_stream_worker.py` reports only what a single frame can measure (vehicle counts,
  PCU); `avg_speed`/`queue_length` are `null` — a frame has no displacement to derive speed from.

### LSTM Forecasting
- `ml/forecasting/` — lazy-loaded. `training_data: "synthetic"` is declared honestly in every
  model-sourced response. The heuristic fallback (`source="heuristic"`) is a persistence baseline
  anchored on the last *measured* reading — it returns 503 rather than inventing a value when
  there's no reading to anchor on.

### A* Routing
- `ml/routing/` + `backend/app/api/routing.py`. Weights in `shared/constants.py::ROUTING_WEIGHTS`.

---

## 9. MQTT Topics & Redis Channels

`shared/constants.py`:
```
MQTT_SENSOR_TELEMETRY_TOPIC   = "surakshanet/sensors/{sensor_id}/telemetry"
MQTT_JUNCTION_TELEMETRY_TOPIC = "surakshanet/junctions/{junction_id}/telemetry"
                                 "surakshanet/junctions/{junction_id}/control"
REDIS_CHANNELS = {...}  # traffic, simulation, signals, emergency, control_commands,
                         # control_decisions, incident_events, event_events,
                         # advisory_events, cv_detections
```
Every MQTT/Redis telemetry payload MUST include a `source` field with a valid `DataSource`
string. The MQTT ingest path (`backend/app/services/mqtt_consumer.py`) accepts only the
measured members (`mqtt|sumo|vision`) on a declared `source` and rejects/logs anything else —
it does not silently relabel or default an unrecognised value.

---

## 10. Development Commands

```bash
# Infrastructure
make up / make down / make build / make dev

# Database
make migrate         # alembic upgrade head (inside Docker)

# Testing
make test            # test-backend + test-frontend
make test-backend    # pytest on 11 backend test files (inside Docker)
make test-frontend   # npm test (frontend/dashboard)
make test-e2e        # E2E suite (Tiers 1-4, inside Docker)

# Code Quality
make lint            # ruff check app/ + npm run build
make format          # ruff format app/

# Validation
make smoke           # scripts/smoke_check.sh — checks /health for "healthy"
make check-phase0    # scripts/check_phase0_regressions.sh — 26 checks, covers Phase 0 + Phase 1 findings

# Orchestrated demo lifecycle (Phase 1, SN-018/020/021)
./start.sh [--profile demo|dev] [--no-frontend] [--seed 42] [--timeout 90]
./stop.sh
./reset.sh            # drop/recreate DB, flush Redis, re-seed, restart from step 0

# Cleanup
make clean
```

### Running Tests Outside Docker
```bash
# Backend — from repo root, PYTHONPATH must include repo root AND backend/
PYTHONPATH=$(pwd):$(pwd)/backend pytest backend/tests/ -v
PYTHONPATH=$(pwd):$(pwd)/backend pytest tests/critical/ -v   # Phase 2 mutation-checked tests

# Frontend — from frontend/dashboard/
npm test
npx tsc --noEmit
npm run build
```

---

## 11. Local Environment State

- `.venv` runs Python **3.14** (`/home/alok/surakshanet/.venv/bin/python3`).
- `.venv` has all core dependencies installed (`torch-2.14.0+cpu`, `sqlalchemy==2.0.52`, `pydantic==2.13.5`, `pytest-asyncio==1.4.0`, `asyncpg==0.31.0`, `geoalchemy2==0.20.0`, etc.).
- `PYTHONPATH=$(pwd):$(pwd)/backend pytest tests/critical/ -v` runs all 24 critical tests with 0 failures in <9 seconds.
- SUMO and `traci` are operational in `.venv`.
- Pre-audit benchmark artifacts were permanently purged and live evaluations are recorded in `ab_runs`.

---

## 12. Pytest Configuration

- `backend/pytest.ini`: `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`
- A second `pytest.ini` exists at the repo root for `tests/critical/` and `tests/e2e/` —
  don't assume backend config applies repo-wide.
- `backend/tests/conftest.py` fixtures:
  - `db_session`: async engine from `settings.DATABASE_URL`, rolled back after each test
  - `client`: `AsyncClient` with ASGI transport, overrides `get_db`
  - `auth_headers`: registers a user, **explicitly promotes to `UserRole.ADMIN` in DB**,
    returns a `Bearer` header — required pattern for admin-gated tests, do not change it
- `tests/e2e/conftest.py`: `authed_client` fixture (attaches an operator token) — use this,
  not a bare `http_client`, for any test against a protected endpoint. An assertion like
  `status_code in (200, 401)` against an *authenticated* client is decorative and blocked by
  the Phase 0 guard.
- `PYTHONPATH` must include the repo root **and** `backend/` (Docker: `/app`; CI:
  `${{ github.workspace }}`; local: repo root + `repo root/backend`) because `ml/`, `shared/`,
  `simulation/`, `services/` sit at repo-root level while `app/` sits under `backend/`.

---

## 13. Critical Invariants (Do Not Change Without Explicit Approval)

1. **Composite PK on `traffic_readings` and `control_decisions`**: `(id, timestamp)` is
   required by the TimescaleDB hypertable. Never change to a single PK.
2. **PostGIS `location` auto-sync**: `Junction.__init__` and `@validates` keep `location`
   synced with `latitude`/`longitude`. Always update both together.
3. **`DataSource` provenance on every payload**: no API response, WS event, or DB write may
   omit or fabricate `source`. The Phase 0/1 regression guard enforces this in CI.
4. **Registration always creates `OPERATOR`**: never allow self-service admin creation.
5. **JWT `jti` revocation via Redis**: `get_current_user()` checks the blacklist on every
   authenticated call. Do not bypass.
6. **Production startup guard**: `validate_production_secrets()` in `config.py`. Do not weaken.
7. **No wildcard CORS**: `sanitize_cors_origins` strips `*`.
8. **ML models are lazy-loaded**: never import `torch`, `ultralytics`, or `xgboost` at module
   level in API routers. Cached getter functions only.
9. **Frontend chunk budget ≤ 500 KB**: `vite.config.ts` `manualChunks` splits (`vendor-maps`,
   `vendor-charts`, `vendor-three-core`, `vendor-three-render`, `vendor-icons`, `vendor-core`,
   `vendor-misc`).
10. **No fallback engine anywhere data would be fabricated**: `/simulation/*`, `/ml/detect`,
    `/ml/predict` all return an honest `503`/unavailable state rather than inventing output when
    their dependency (SUMO, YOLO weights, trained model) is absent. Do not add a "graceful"
    fallback that produces plausible-looking numbers — that is the exact defect class Phase 0
    exists to eliminate.
11. **`sumo_env.py` raises `ImportError`, not `SystemExit`, on missing traci** — its callers
    depend on catching it. The hard `SystemExit` guard (`shared/sumo_bootstrap.py::require_traci()`)
    belongs only to process entrypoints — `backend/app/main.py`, `simulation/sumo_live_bridge.py`,
    `services/control_service/main.py` — never to a library module another try/except relies on.
12. **Alembic migrations run under a Postgres advisory lock, and a real failure must propagate**:
    `backend/app/database.py::_run_migrations_once()`. Do not wrap the migration call in a bare
    `except Exception: logger.info(...)` again — that previously masked genuine failures as
    "already applied," letting the app boot on a broken schema while `/health/deep` still
    reported `postgres: ok`.
13. **`/health` returns `{"status": "healthy"}`**, not `"ok"` — `scripts/smoke_check.sh` and
    `tests/e2e/.../test_f29_smoke_checks.py` hard-check this exact string. `/health/deep` has
    its own separate `ok`/`degraded`/`error`/`unavailable` vocabulary; don't conflate the two.
14. **A checklist task is `DONE` only when its Definition-of-Done conditions hold**
    (`docs/23-final-acceptance.md §1`: implemented ∧ integrated ∧ tested ∧ demonstrated ∧
    documented) — never mark a task complete because the code exists and compiles. See §1's
    note on Phase 2's current inconsistent tracker state.

---

## 14. Fragile Areas (Inspect Carefully Before Modifying)

| File | Risk | Notes |
|---|---|---|
| `simulation/sumo_live_bridge.py` | HIGH | 20KB complex TraCI bridge; verify TraCI API compatibility on any change; uses the hard `require_traci()` guard intentionally |
| `services/control_service/ab_runner.py` | HIGH | SN-038's headline evidence generator — never adjust it to produce a more favorable number; a negative result is a valid, required-to-report outcome |
| `ml/marl/train_marl.py` | HIGH | Currently trains on synthetic `np.random` data, not SUMO (SN-012f, open) — any performance claim sourced from its output is unverified until fixed |
| `backend/app/main.py` | MEDIUM | Mid-file imports after SUMO path injection — acknowledged debt |
| `backend/app/models/junction.py` | MEDIUM | GeoAlchemy2 SQLite monkey-patch at top of file for spatialite-less test runs |
| `backend/tests/conftest.py` | MEDIUM | Admin role elevation pattern required by many tests — changing breaks test isolation |
| `ml/marl/webster_fallback.py` | HIGH | Phase-string generation must match the TraCI signal program length exactly for the current topology |
| `backend/alembic/versions/` | HIGH | Migrations are irreversible in production; always test against a copy first |
| `ml/benchmarks/results/`, `docs/RESEARCH_DEFENSE.md`, `STATUS.md` | HIGH — but for trust, not code | Contains fabricated pre-audit content; see §1. Do not extend or cite from these until `docs/26-phase2-remediation-plan.md` item 6 lands |

---

## 15. Shared Constants (single source of truth)

`shared/constants.py`: `DataSource` enum (6 values) · `PCU_FACTORS` (car=1.0, motorcycle=0.5,
bus=3.0, truck=3.0, auto_rickshaw=1.0, bicycle=0.2, lcv=1.5) · `SIGNAL_CONSTRAINTS` (min_green=10s,
max_green=60s, amber=3s, all_red=2s) · `ALERT_THRESHOLDS` · `MARL_HYPERPARAMS` · `ROUTING_WEIGHTS` ·
`EMERGENCY_CONFIG` · `MQTT_*_TOPIC` constants · `REDIS_CHANNELS` (new, Phase 2) · `DEMO_SEED = 42`.

`shared/sumo_bootstrap.py` (new, Phase 1): `ensure_sumo_on_path()`, `require_traci()` — the
single place the SUMO sys.path setup and the hard traci-import guard live; four process
entrypoints call into it rather than each re-implementing the block.

`shared/paths.py` (new, Phase 1): `find_existing()`, `resolve_repo_path()` — the single place
"search N candidate directories for a file" lives; used by `health.py`'s weight-file checks and
`api/simulation.py`'s net/route/detector-file resolution.

`shared/telemetry.py` (new, Phase 2): `ApproachTelemetry`, `JunctionTelemetry`, `validate_telemetry`
— the canonical schema every telemetry producer (bridge, MQTT consumer, control service) must emit.

`shared/exceptions.py`: `VisionUnavailable` — raised, never silently substituted for, when the
vision pipeline has no real detection to report.

---

## 16. Coding Conventions

- **Python**: 120-char line limit (ruff.toml). Type hints everywhere. `async/await` throughout backend.
- **SQLAlchemy**: Classic `Column[]` style (not `Mapped[]`).
- **Pydantic v2**: `model_validator`/`field_validator`, not the deprecated `@validator`.
- **FastAPI**: All dependencies via `Depends()`. Router-level prefixes. Always specify `response_model`.
- **Frontend**: TypeScript strict mode. `React.lazy()` for route-level pages. Avoid `any`.
- **Never add a graceful fallback that fabricates plausible-looking data** — return the honest
  unavailable/error state instead (Invariant §13.10). This is the single most load-bearing
  convention in this codebase; every Phase 0/1 defect found in review was a violation of it.
- **Tests**: use `conftest.py` fixtures; no parallel fixture patterns; `pytest-asyncio` for async.
  A test asserting a status code range that passes whether or not the feature works (e.g.
  `status_code in (200, 401)` against an authenticated client) is decorative and will be flagged.

---

## 17. Task Workflow (Follow for Every Task)

1. **Understand** the request fully.
2. **Read relevant sections of this file** — check §1 for current phase status before assuming
   anything is done.
3. **Run `git status` and `git diff`** — this repo is sometimes modified by concurrent sessions;
   don't trust your last read of a file without re-checking if meaningful time has passed.
4. **Identify the minimal file set** to inspect.
5. **Inspect those files** and their direct dependencies only.
6. **Make the change**, following Invariant §13.10 above all else: no fabricated fallback data.
7. **Review `git diff`** before finalizing.
8. **Run validations**: backend → `ruff check app/` + `pytest tests/test_<area>.py -v`; frontend →
   `npx tsc --noEmit` + `npm test` + `npm run build`; DB model change → Alembic migration +
   `alembic upgrade head`; any change touching a fabrication-adjacent area → `make check-phase0`.
9. **Report** what changed, what was tested, and what remains unverified — do not mark a task
   `DONE` in `docs/CHECKLIST.md` without satisfying its literal acceptance line (§13.14).

---

## 18. Environment Variables Reference

| Variable | Default | Production Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` triggers secret validation at startup |
| `JWT_SECRET_KEY` | `your-super-secret-key-...` | Min 16 chars |
| `DATABASE_URL` | assembled from parts | `postgresql+asyncpg://...@timescaledb:5432/surakshanet` |
| `REDIS_URL` | `redis://redis:6379/0` | Add password in prod |
| `MQTT_BROKER_HOST` | `mosquitto` | Internal Docker service name |
| `MQTT_BROKER_PORT` | `1883` | |
| `CORS_ORIGINS` | localhost variants | JSON array or comma-separated; never `*` |
| `ADMIN_EMAIL` | `admin@surakshanet.local` | Seeded once on first startup |
| `ADMIN_PASSWORD` | `SurakshaNet@2026` | Must be changed in production; never hardcode elsewhere (test fixtures skip rather than default — §6) |
| `SUMO_HOME` | `/usr/share/sumo` | |
| `WORKERS` | `2` | Migration races handled via advisory lock (§13.12) |

---

## 19. Known Technical Debt

| Item | Location | Resolution Path |
|---|---|---|
| `.venv` missing `torch`/`sqlalchemy`, running 3.14 not 3.11 | local dev environment | `docs/26-phase2-remediation-plan.md` item 2 |
| MARL trained on synthetic data, not SUMO | `ml/marl/train_marl.py` (SN-012f) | `docs/26-phase2-remediation-plan.md` item 4 |
| A/B harness never executed | `services/control_service/ab_runner.py` (SN-038) | item 5, depends on item 4 |
| Fabricated pre-audit benchmark artifacts | `ml/benchmarks/results/`, `docs/RESEARCH_DEFENSE.md`, `STATUS.md` | item 6 |
| Checklist self-inconsistency (per-task `COMPLETE` vs. phase rollup `0/17`) | `docs/CHECKLIST.md` | item 1 |
| Badge coverage incomplete (SN-012g) | most numeric UI panels have no `<TelemetrySourceBadge>` | P1, not yet scheduled |
| ~34 mypy advisory errors | `backend/app/models/` | `Column[]` → `Mapped[]` refactor, later phase |
| Frontend test scope | `src/store/authStore.test.js` | Vitest expansion planned |

---

## 20. Documentation Cross-Reference

| Topic | Reference |
|---|---|
| Architecture deep-dive | `docs/02-system-architecture.md` |
| API contracts | `docs/06-api-contracts.md` |
| Database schema | `docs/05-database.md` |
| MARL & signal control spec | `docs/08-marl-control.md` |
| Telemetry & provenance | `docs/07-telemetry.md` |
| Phase 1 remediation (done) | `docs/25-phase1-remediation-plan.md` |
| Phase 2 remediation (open) | `docs/26-phase2-remediation-plan.md` |
| Final acceptance / Definition of Done | `docs/23-final-acceptance.md` |
| Environment setup | `docs/04-environment-setup.md` |
| Master checklist | `docs/CHECKLIST.md` (large — grep, don't read in full; verify per-task status against §1's caveat) |
| **Do not cite as fact** | `STATUS.md`, `docs/RESEARCH_DEFENSE.md`, `ml/benchmarks/results/*` — see §1 |

---

## 21. Context Update Rule

Update only the relevant section of this file when discovering:
- New stable architectural decisions or constraints
- Important invariants or patterns not captured here
- Corrections to documented information — including corrections to *this file*, if a claim in
  it turns out to be stale or wrong. Verify against the code before writing a claim here; this
  file drifting from reality (as §1's "known contamination" note describes for other project
  docs) is exactly the failure mode it exists to prevent elsewhere.

**Do NOT add** temporary task-specific details, per-session notes, or in-progress work to this
file. Status belongs in `docs/CHECKLIST.md`; this file is architecture and invariants, not a log.
