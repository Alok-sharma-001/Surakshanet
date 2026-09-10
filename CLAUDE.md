# CLAUDE.md — Surakshanet ITS: Persistent Operating Instructions

> This file is the **persistent source of project knowledge** for Claude Code sessions.
> Before broad codebase exploration, always check this file and `git status`/`git diff` first.
> Update this file when discovering stable architectural knowledge or important design constraints.

---

## 1. Project Identity

**Surakshanet** is an Intelligent Transportation System (ITS) for urban traffic monitoring, spatial junction management, adaptive signal optimization, and operator observability. It is undergoing a **10-phase architectural hardening** per an independent code audit tracked across milestones M1–M7 (see `PROJECT.md` and `docs/CHECKLIST.md`).

Current branch status (as of analysis):
- **M1 (Security):** DONE
- **M2 (Data Integrity & Spatial Storage):** IN_PROGRESS (`phase0/complete` branch)
- **M3–M7:** PLANNED

---

## 2. Repository Layout

```
surakshanet/
├── backend/             # FastAPI application (Python 3.11)
│   ├── app/             # Core application code
│   │   ├── api/         # Route handlers (REST + WebSocket)
│   │   ├── config.py    # Pydantic Settings (reads .env)
│   │   ├── database.py  # SQLAlchemy async engine + Alembic runner
│   │   ├── main.py      # FastAPI app factory, lifespan, middleware
│   │   ├── middleware/  # CorrelationId, Prometheus metrics
│   │   ├── models/      # SQLAlchemy ORM models (GeoAlchemy2)
│   │   ├── schemas/     # Pydantic v2 request/response schemas
│   │   ├── services/    # Business logic (auth, traffic, MQTT)
│   │   └── websocket/   # ConnectionManager (manager.py)
│   ├── alembic/         # Alembic migration environment + versions/
│   ├── alembic.ini      # Alembic config (script_location = alembic/)
│   ├── tests/           # Pytest suite (asyncio_mode = auto)
│   ├── ruff.toml        # Ruff linter config (staged rule set)
│   └── .flake8          # Flake8 config
├── frontend/
│   └── dashboard/       # React 18 + TypeScript + Vite SPA
│       ├── src/
│       │   ├── App.tsx        # Router with React.lazy code splitting
│       │   ├── components/    # ErrorBoundary, TelemetrySourceBadge, Layout
│       │   ├── pages/         # 18 route-level page components (code-split)
│       │   ├── services/      # API client (axios) + WebSocket client
│       │   ├── store/         # Zustand state stores
│       │   └── types/         # Generated/hand-written TypeScript types
│       ├── vite.config.ts     # Build config with manual chunk splitting
│       └── package.json
├── ml/                  # Machine learning pipelines
│   ├── marl/            # DQN agent, coordinator, Webster fallback, weights/
│   ├── vision/          # YOLOv8 vehicle detection
│   ├── forecasting/     # LSTM traffic forecaster
│   ├── emergency/       # Green-wave preemption logic
│   ├── routing/         # A* pathfinding
│   └── benchmarks/      # Webster vs MARL baseline study runner
├── simulation/          # Eclipse SUMO + TraCI bridge
│   ├── sumo_env.py          # TraCI environment wrapper
│   ├── sumo_live_bridge.py  # Live simulation bridge (FRAGILE — 20 KB)
│   ├── network_generator.py
│   └── networks/            # SUMO network XML files
├── shared/              # Cross-module constants and schemas
│   ├── constants.py     # DataSource enum, PCU_FACTORS, MQTT topics, MARL hyperparams
│   ├── schemas.py       # Shared Pydantic schemas
│   └── exceptions.py
├── infra/               # Docker Compose + Nginx + Prometheus + Grafana + Mosquitto
│   ├── docker-compose.yml       # Dev: timescaledb, redis, mosquitto
│   ├── docker-compose.prod.yml  # Production stack
│   └── docker-compose.demo.yml  # Demo stack
├── iot/                 # IoT edge device simulation/telemetry
├── services/            # Background/control services (control_service/)
├── scripts/             # Operational scripts
│   ├── smoke_check.sh
│   ├── check_phase0_regressions.sh
│   ├── backup_db.sh
│   └── purge_history.sh
├── tests/e2e/           # Opaque-box E2E suite (326 test cases, Tiers 1–4)
├── docs/                # 29 specification documents (00–25 + CHECKLIST.md)
├── .env                 # Local secrets (gitignored)
├── .env.example         # Environment variable template
├── Makefile             # Primary developer command interface
└── .github/workflows/   # CI: ci.yml, deploy.yml
```

---

## 3. Technology Stack

### Backend
| Layer | Technology |
|---|---|
| Framework | FastAPI 0.104.1 (async) |
| Python | 3.11 |
| ORM | SQLAlchemy 2.0 (async/asyncpg) |
| DB Driver | asyncpg (PostgreSQL), aiosqlite (test fallback) |
| Migrations | Alembic 1.13 |
| Spatial | GeoAlchemy2 + PostGIS (`Geometry('POINT', srid=4326)`) |
| Time-series | TimescaleDB hypertables |
| Auth | JWT (HS256) via `python-jose`, bcrypt via `passlib` |
| Messaging | Redis pub/sub (redis-py asyncio), paho-mqtt |
| ML | PyTorch, Ultralytics YOLOv8, XGBoost, scikit-learn |
| Simulation | Eclipse SUMO + TraCI (`traci>=1.19`, `eclipse-sumo>=1.19`) |
| Metrics | Prometheus (`prometheus-client`) |
| Validation | Pydantic v2 + pydantic-settings |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite 5, tsc |
| Routing | react-router-dom v6 (React.lazy code splitting) |
| State | Zustand 4 |
| HTTP | axios |
| Maps | Leaflet + react-leaflet, mapbox-gl |
| Charts | Recharts |
| 3D | Three.js |
| Styling | Tailwind CSS 3 (light theme — see `design.md`) |
| Testing | Vitest + React Testing Library + jsdom |
| Animation | framer-motion |

### Infrastructure
| Service | Image | Host Port |
|---|---|---|
| TimescaleDB + PostGIS | `timescale/timescaledb-ha:pg15` | 5432 |
| Redis | `redis:7-alpine` | 6379 (127.0.0.1 only) |
| Mosquitto MQTT | `eclipse-mosquitto:2` | 1883 (127.0.0.1 only) |
| FastAPI Backend | custom Dockerfile | 8000 |
| Prometheus | official | 9090 |
| Grafana | official | 3000 |
| Nginx | official | 80/443 |

---

## 4. Database Schema

### Key Tables

**`users`** — Authentication and RBAC
- `id` UUID PK, `email` (unique, indexed), `password_hash`, `name`
- `role`: enum `ADMIN | OPERATOR | VIEWER` (default: `VIEWER`)
- Registration always creates `OPERATOR`; admin promotes via `PATCH /api/v1/users/{id}/role`

**`junctions`** — Spatial junction master
- `id` UUID PK, `name`, `latitude` Float, `longitude` Float
- `location`: `Geometry('POINT', srid=4326)` with GiST spatial index — auto-synced from lat/lon via `__init__` and `@validates`
- `is_active`, `num_approaches` (default 4), `geometry` JSON

**`traffic_sensors`** — Sensor registry per junction
- `sensor_type`: `CAMERA | INDUCTION | ACOUSTIC | GPS`
- `approach_direction`: `N | E | S | W`
- FK to `junctions.id` (CASCADE DELETE)

**`traffic_readings`** — TimescaleDB hypertable (time-series telemetry)
- Composite PK: `(id UUID, timestamp DateTime)` — required for hypertable
- `vehicle_count`, `pcu_value`, `avg_speed`, `queue_length`, `vehicle_breakdown` JSON
- `source` string — must match a `DataSource` enum value
- Chunk interval: 1 day; retention policy: 90 days

**`alerts`** — Traffic alerts
- `alert_type`: `CONGESTION | SPILLBACK | SIGNAL_FAILURE | QUEUE_OVERFLOW`
- `severity`: `INFO | WARNING | CRITICAL`

**`emergency_events`** — Emergency vehicle preemption records
- `vehicle_type`: `AMBULANCE | FIRE | POLICE | VIP`
- `priority`: `CRITICAL | HIGH | MEDIUM`
- `status`: `ACTIVE | COMPLETED | CANCELLED`
- `route` JSON array of junction IDs

### Alembic Migrations
- Config: `backend/alembic.ini`; migrations in `backend/alembic/versions/`
- Two existing: `001_initial_schema.py`, `001b_datasource_provenance.py`
- `database.py:init_db()` runs Alembic automatically on startup (PostgreSQL) and uses `create_all` for SQLite test fallback

---

## 5. API Architecture

### REST Endpoints (all under `/api/v1`)

| Router | File | Key Endpoints |
|---|---|---|
| `/auth` | `api/auth.py` | `POST /register`, `POST /login`, `POST /logout` |
| `/users` | `api/users.py` | `PATCH /{user_id}/role` (ADMIN only) |
| `/traffic` | `api/traffic.py` | CRUD for readings, sensor data |
| `/junctions` | `api/junctions.py` | Junction management with spatial queries |
| `/ml` | `api/ml.py` | `POST /ml/detect` (YOLOv8), forecasting, signal inference |
| `/simulation` | `api/simulation.py` | SUMO TraCI control |
| `/routing` | `api/routing.py` | A* pathfinding with congestion weights |
| `/alerts` | `api/alerts.py` | Alert CRUD and acknowledgment |
| `/emergency` | `api/emergency.py` | `POST /activate`, `POST /deactivate/{vehicle_id}` |
| `/signals` | `api/signals.py` | Signal plan management (Webster/MARL/Manual) |
| `/health` | `api/health.py` | Health check (also at root `/`) |
| `/metrics` | `main.py` | Prometheus scrape endpoint (no prefix) |

### WebSocket Endpoints (no `/api/v1` prefix)
```
/ws/traffic       → channel: 'traffic'
/ws/signals       → channel: 'signals'
/ws/alerts        → channel: 'alerts'
/ws/emergency     → channel: 'emergency'
/ws/training      → channel: 'training'
/ws/{channel}     → dynamic channel
/api/v1/ws        → channel: 'default'
```

WebSockets are managed by `app/websocket/manager.py::ConnectionManager` (singleton `manager`). Cross-worker broadcast uses Redis pub/sub. `redis_pubsub_bridge()` coroutine in `main.py` subscribes to Redis channels and dispatches to local WebSocket clients via `manager.local_broadcast()`.

### Error Response Envelope
```json
{
  "detail": "...",
  "error": {
    "code": 422,
    "message": "...",
    "details": "...",
    "request_id": "<uuid>"
  }
}
```
Every response carries `X-Request-ID` header (injected by `CorrelationIdMiddleware`).

---

## 6. Authentication & Security

- **JWT**: HS256, `python-jose`. Claims include `jti` (UUID) for individual revocation.
- **Token revocation**: Redis key `revoked_token:{jti}` with TTL = remaining lifetime. `POST /api/v1/auth/logout` triggers this. `get_current_user()` checks Redis on every request.
- **Rate limiting**: Lockout after 5 consecutive failures tracked in Redis (`auth:failed_logins:{email}`).
- **RBAC**: Three roles — `ADMIN`, `OPERATOR`, `VIEWER`. Registration always creates `OPERATOR`. Promotion to ADMIN requires explicit admin action.
- **Production startup guard**: `config.py::validate_production_secrets()` blocks startup with default `JWT_SECRET_KEY`, `ADMIN_PASSWORD`, or dev DB credentials when `ENVIRONMENT=production`.
- **CORS**: Whitelist via `settings.CORS_ORIGINS`; `sanitize_cors_origins` strips any `*` origins.

---

## 7. Data Provenance Contract (MANDATORY)

Every telemetry payload, WebSocket frame, and `traffic_readings.source` value MUST carry a `DataSource`:

| Enum Value | String | Meaning |
|---|---|---|
| `DataSource.SUMO` | `"sumo"` | Measured from SUMO microsimulation via TraCI |
| `DataSource.VISION` | `"vision"` | Derived from camera frames by YOLOv8 detector |
| `DataSource.MQTT` | `"mqtt"` | Reported by physical/simulated edge device |
| `DataSource.MODEL` | `"model"` | Produced by trained model (LSTM, DQN) |
| `DataSource.HEURISTIC` | `"heuristic"` | Produced by formula (Webster), NOT trained |
| `DataSource.MANUAL` | `"manual"` | Entered or seeded by a human |

Dashboard `<TelemetrySourceBadge>`: LIVE=green, SIM=blue, MOCK=amber.

**NEVER fabricate, hardcode, or fake data values in API responses, tests, or UI components.**
The Phase 0 regression guard (`scripts/check_phase0_regressions.sh`) enforces this in CI.

---

## 8. ML & Simulation Subsystems

### MARL (Multi-Agent Reinforcement Learning)
- Location: `ml/marl/`
- DQN agents coordinate 4-junction arterial corridor
- 18-link SUMO network; phase strings are **exactly 18 characters** (e.g., `rrrrGGGggrrrrGGGgg`)
- Webster fallback: `ml/marl/webster_fallback.py` — produces 18-char phase strings from lane flow data
- Benchmark results: 18.38% delay reduction, 22.92% queue reduction over Webster
- Weights stored in `ml/marl/weights/`

### SUMO / TraCI
- Location: `simulation/`
- `sumo_env.py`: TraCI environment wrapper
- `sumo_live_bridge.py`: Live bridge (**20 KB — inspect carefully before modifying**)
- Requires SUMO binary; graceful degradation to `MicroSimRunner` when absent (tags output `source: "sim"`)
- Corridor: 4 junctions, 18 links — topology change requires updating phase strings

### YOLOv8 Vision
- Location: `ml/vision/`
- CPU-optimized `yolov8n`; lazy-loaded via cached getter
- Accessed via `POST /api/v1/ml/detect` (frame upload)

### LSTM Forecasting
- Location: `ml/forecasting/`; lazy-loaded on demand

### A* Routing
- Location: `ml/routing/` + `backend/app/api/routing.py`
- Congestion cost weights defined in `shared/constants.py::ROUTING_WEIGHTS`

---

## 9. MQTT Topics

Defined in `shared/constants.py`:
```
surakshanet/sensors/{sensor_id}/telemetry
surakshanet/junctions/{junction_id}/telemetry
surakshanet/junctions/{junction_id}/control   (signal cabinet commands)
```
Every MQTT payload MUST include `"source"` field with a valid `DataSource` string.

---

## 10. Development Commands

```bash
# Infrastructure
make up              # start all Docker services (background)
make down            # stop all services
make build           # rebuild Docker images
make dev             # alias for 'up'

# Database
make migrate         # alembic upgrade head (inside Docker)

# Testing
make test            # test-backend + test-frontend
make test-backend    # pytest on 11 backend test files (inside Docker)
make test-frontend   # npm test (frontend/dashboard)
make test-e2e        # 326-case E2E suite (Tiers 1-4, inside Docker)

# Code Quality
make lint            # ruff check app/ + npm run build (type-check + build)
make format          # ruff format app/

# Validation
make smoke           # smoke_check.sh on /health, /metrics, WebSocket
make check-phase0    # regression guard for fabrication patterns

# Cleanup
make clean           # remove __pycache__, *.pyc, frontend/dist
```

### Running Tests Outside Docker (local / CI)
```bash
# Backend (from backend/ — PYTHONPATH must include repo root)
PYTHONPATH=/home/alok/surakshanet pytest tests/ -v
PYTHONPATH=/home/alok/surakshanet pytest tests/test_auth.py -v

# Frontend (from frontend/dashboard/)
npm test
npx tsc --noEmit
npm run build
```

### Lint & Type Check
```bash
# Backend (from backend/)
ruff check app/                     # blocking in CI (E4/E7/E9/F rules)
flake8 app/                         # supplementary
mypy app/ --ignore-missing-imports  # advisory only

# Frontend (from frontend/dashboard/)
npx tsc --noEmit
```

---

## 11. Pytest Configuration

- `backend/pytest.ini`: `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`
- `backend/tests/conftest.py` fixtures:
  - `db_session`: Creates async engine from `settings.DATABASE_URL`; rolls back after each test
  - `client`: `AsyncClient` with ASGI transport; overrides `get_db` dependency
  - `auth_headers`: Registers user → **explicitly promotes to `UserRole.ADMIN` in DB** → returns `Bearer` header
- **Critical**: `auth_headers` role promotion pattern is required for admin-gated tests. Do not change this pattern.
- `PYTHONPATH` must include repo root (Docker: `/app`; CI: `${{ github.workspace }}`; local: repo root) because `ml/`, `shared/`, `simulation/` are at root level.

---

## 12. CI Pipeline (`.github/workflows/ci.yml`)

Triggers: push/PR to `main`. Three jobs:

1. **phase0-guard**: `scripts/check_phase0_regressions.sh` — ensures no fabricated data patterns re-appear
2. **backend** (Python 3.11):
   - `ruff check app/` + `flake8 app/` (blocking)
   - `mypy app/ --ignore-missing-imports` (advisory, `continue-on-error: true`)
   - `alembic upgrade head`
   - `pytest tests/ -v --cov=app`
3. **frontend** (Node.js 20):
   - `npx tsc --noEmit`
   - `npm test`
   - `npm run build`

Pinned CI tool versions: `ruff==0.16.6`, `flake8==7.1.1`, `mypy==1.13.0`.

---

## 13. Critical Invariants (Do Not Change Without Explicit Approval)

1. **SUMO 18-character phase strings**: 4-junction corridor has exactly 18 links. Phase strings must be exactly 18 chars. Breaking this crashes TraCI.
2. **Composite PK on `traffic_readings`**: `(id, timestamp)` is required by TimescaleDB hypertable. Never change to single PK.
3. **PostGIS `location` auto-sync**: `Junction.__init__` and `@validates` keep `location` synced with `latitude`/`longitude`. Always update both together.
4. **`DataSource` provenance on every payload**: No API response, WS event, or DB write may omit or fabricate the `source` field. Phase 0 regression guard enforces this.
5. **Registration always creates `OPERATOR` role**: `register_user()` ignores any role in the request body. Never allow self-service admin creation.
6. **JWT `jti` revocation via Redis**: `get_current_user()` checks Redis blacklist on every authenticated call. Do not bypass.
7. **Production startup guard**: `validate_production_secrets()` in `config.py`. Do not weaken or remove.
8. **No wildcard CORS**: `sanitize_cors_origins` strips `*`. Never allow wildcard in production config.
9. **ML models are lazy-loaded**: Never import `torch`, `ultralytics`, or `xgboost` at module level in API routers. Use cached getter functions only.
10. **Frontend chunk budget ≤ 500 KB**: `vite.config.ts` `manualChunks` defines splits: `vendor-maps`, `vendor-charts`, `vendor-three-core`, `vendor-three-render`, `vendor-icons`, `vendor-core`, `vendor-misc`.

---

## 14. Fragile Areas (Inspect Carefully Before Modifying)

| File | Risk | Notes |
|---|---|---|
| `simulation/sumo_live_bridge.py` | HIGH | 20 KB complex TraCI bridge; verify TraCI API compatibility on any change |
| `backend/app/main.py` | MEDIUM | Mid-file imports after SUMO path injection — acknowledged debt; ruff E402 exception intentional |
| `backend/app/models/junction.py` | MEDIUM | GeoAlchemy2 SQLite monkey-patch at top of file for spatialite-less test runs; E402 ignore intentional |
| `backend/tests/conftest.py` | MEDIUM | Admin role elevation pattern required by many tests — changing breaks test isolation |
| `ml/marl/webster_fallback.py` | HIGH | 18-char phase string generation must match TraCI signal program length exactly |
| `backend/alembic/versions/` | HIGH | Schema migrations are irreversible in production; always test against a copy first |

---

## 15. Shared Constants (single source of truth)

`shared/constants.py`:
- `DataSource` enum (6 values)
- `PCU_FACTORS`: car=1.0, motorcycle=0.5, bus=3.0, truck=3.0, auto_rickshaw=1.0, bicycle=0.2, lcv=1.5
- `SIGNAL_CONSTRAINTS`: min_green=10s, max_green=60s, amber=3s, all_red=2s
- `ALERT_THRESHOLDS`: congestion_density=80%, speed=15 km/h, spillback_risk=0.85, signal_timeout=10s
- `MARL_HYPERPARAMS`: buffer=10000, batch=32, gamma=0.99, lr=0.001
- `ROUTING_WEIGHTS`: travel_time=0.4, congestion=0.3, distance=0.3
- `EMERGENCY_CONFIG`: lookahead=3 junctions, green_hold=30s
- `MQTT_SENSOR_TELEMETRY_TOPIC`, `MQTT_JUNCTION_TELEMETRY_TOPIC`
- `DEMO_SEED = 42` (deterministic seed for reproducibility)

---

## 16. Coding Conventions

- **Python**: 120-char line limit (ruff.toml). Type hints everywhere. `async/await` throughout backend.
- **SQLAlchemy**: Classic `Column[]` style (not `Mapped[]` — migration would require dedicated refactor; mypy has ~34 advisory warnings on this).
- **Pydantic v2**: Use `model_validator`, `field_validator` — not the deprecated `@validator`.
- **FastAPI**: All dependencies via `Depends()`. Router-level prefixes. Always specify `response_model`.
- **Frontend**: TypeScript strict mode. `React.lazy()` for all route-level pages wrapped in `<Suspense>`. Avoid `any` in `api.ts`, `websocket.ts`, and page components.
- **Tailwind**: Light theme, defined in `design.md`. Token: `primary-600` for primary actions, `neutral-*` for text.
- **Tests**: Use `conftest.py` fixtures. No parallel fixture patterns. `pytest-asyncio` for all async tests.

---

## 17. Task Workflow (Follow for Every Task)

1. **Understand** the request fully.
2. **Read relevant sections** of this file.
3. **Run `git status` and `git diff`** to see what has changed.
4. **Identify the minimal file set** to inspect (avoid full codebase scans).
5. **Inspect those files** and their direct dependencies only.
6. **Make the change** following existing patterns.
7. **Review `git diff`** of changes before finalizing.
8. **Run appropriate validations**:
   - Backend change → `ruff check app/` + `pytest tests/test_<area>.py -v`
   - Frontend change → `npx tsc --noEmit` + `npm test` + `npm run build`
   - DB model change → generate Alembic migration + `alembic upgrade head`
   - Any change → `make smoke` if services are running
9. **Report** what changed, what was tested, and any remaining concerns.

---

## 18. Environment Variables Reference

| Variable | Default | Production Notes |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` triggers secret validation at startup |
| `JWT_SECRET_KEY` | `your-super-secret-key-...` | Min 16 chars; generate with `openssl rand -hex 32` |
| `DATABASE_URL` | assembled from parts | `postgresql+asyncpg://...@timescaledb:5432/surakshanet` |
| `REDIS_URL` | `redis://redis:6379/0` | Add password (`redis://:pass@redis:6379/0`) in prod |
| `MQTT_BROKER_HOST` | `mosquitto` | Internal Docker service name |
| `MQTT_BROKER_PORT` | `1883` | |
| `CORS_ORIGINS` | localhost variants | JSON array or comma-separated; never `*` |
| `ADMIN_EMAIL` | `admin@surakshanet.local` | Seeded once on first startup |
| `ADMIN_PASSWORD` | `SurakshaNet@2026` | Must be changed in production |
| `SUMO_HOME` | `/usr/share/sumo` | Path to SUMO installation |
| `WORKERS` | `2` | Uvicorn worker processes |

Secret generation script: `infra/scripts/generate_secrets.sh`

---

## 19. Known Technical Debt

| Item | Location | Resolution Path |
|---|---|---|
| ~34 mypy advisory errors | `backend/app/models/` | SQLAlchemy `Column[]` → `Mapped[]` migration (dedicated refactor) |
| Mid-file imports in `main.py` | `backend/app/main.py` | Cleanup after SUMO path injection concerns resolved |
| Ruff staged rule set | `backend/ruff.toml` | Only E4/E7/E9/F active; I (imports) + UP + B planned for later phases |
| MARL not in live inference loop | `services/control_service/` | DQN weights exist; live loop planned for M3 |
| Emergency corridor | `docs/10-emergency-corridor.md` | Planned Phase 3 |
| Public citizen advisory API | `docs/12-citizen-advisory.md` | Planned Phase 4 |
| Frontend test scope | `src/store/authStore.test.js` | `npm test` runs Node test runner on this single file; Vitest expansion planned |

---

## 20. Documentation Cross-Reference

| Topic | Reference |
|---|---|
| Architecture deep-dive | `docs/02-system-architecture.md` |
| API contracts | `docs/06-api-contracts.md` |
| Database schema | `docs/05-database.md` |
| MARL & signal control | `docs/08-marl-control.md` |
| Emergency corridor spec | `docs/10-emergency-corridor.md` |
| Telemetry & provenance | `docs/07-telemetry.md` |
| Frontend spec | `docs/24-frontend.md` |
| Security & privacy | `docs/17-security-privacy.md` |
| RBAC | `docs/16-rbac.md` |
| Current subsystem status | `docs/01-current-state.md` |
| Milestone checklist | `docs/CHECKLIST.md` (119 KB — use grep, do not read in full) |
| Environment setup | `docs/04-environment-setup.md` |
| Milestone/feature tracking | `PROJECT.md` |
| Project status matrix | `STATUS.md` |

---

## 21. Context Update Rule

Update only the relevant section of this file when discovering:
- New stable architectural decisions or constraints
- Important invariants or patterns not captured here
- Corrections to documented information

**Do NOT add** temporary task-specific details, per-session notes, or in-progress work to this file.
