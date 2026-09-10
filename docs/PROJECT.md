# Project: Surakshanet ITS Transformation

## Architecture
Surakshanet is an Intelligent Transportation System (ITS) platform comprising:
1. **Backend Service (`backend/app`)**: FastAPI asynchronous application providing REST APIs, WebSockets, background event ingestion, and telemetry services.
2. **Database Engine (`timescaledb-ha:pg15`)**: Consolidated PostgreSQL 15 engine with PostGIS 3.6+ for spatial junction geometry and TimescaleDB for time-series traffic telemetry hypertables.
3. **Message & Cache Broker (`redis:7-alpine`)**: Redis pub/sub for cross-worker WebSocket broadcast fanout, task queue synchronization, and JWT token revocation blacklisting.
4. **IoT & Edge Simulation (`iot/`, `simulation/`)**: MQTT telemetry ingestion, SUMO microscopic corridor simulation (TraCI), and synthetic/sensor data pipelines tagged with origin metadata (`source: "live" | "sim" | "mock"`).
5. **Machine Learning Pipelines (`ml/`)**: Multi-Agent Reinforcement Learning (DQN) traffic signal controllers, Webster analytical fixed-time baselines, LSTM traffic forecasters, YOLOv8 vision detection, and dynamic green-wave topology preemption. Heavyweight models lazy-loaded on demand.
6. **Frontend Dashboard (`frontend/dashboard`)**: React 18 + TypeScript + Vite dashboard featuring code-split routes, light-theme design system (`design.md`), real-time WebSocket subscriptions with exponential backoff, and telemetry origin indicators.
7. **Reverse Proxy & Edge (`infra/nginx`)**: Nginx reverse proxy enforcing HTTPS redirection, SSL termination, and secure CORS headers.

```
                  ┌───────────────────────────────┐
                  │      React Dashboard (Vite)   │
                  └───────────────▲───────────────┘
                                  │ HTTPS / WSS
                  ┌───────────────▼───────────────┐
                  │       Nginx Reverse Proxy     │
                  └───────────────▲───────────────┘
                                  │
         ┌────────────────────────┴────────────────────────┐
         │                                                 │
┌────────▼────────────────┐                      ┌─────────▼──────────────┐
│  FastAPI Web Workers    │                      │  Background Workers    │
│  (Auth, APIs, WebSockets│                      │  (Simulation, ML Tasks)│
└────────┬────────┬───────┘                      └─────────┬──────────────┘
         │        │                                        │
         │        └───────────────┐       ┌────────────────┘
         │                        │       │
┌────────▼────────┐      ┌────────▼───────▼───────┐      ┌────────────────────────┐
│  TimescaleDB-HA │      │      Redis Pub/Sub     │◄─────┤ MQTT Telemetry / SUMO  │
│(PostGIS + Hyper)│      │(Fanout, Revoke, Queues)│      │ (live, sim, mock)      │
└─────────────────┘      └────────────────────────┘      └────────────────────────┘
```

---

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Operator-Only Registration | Restrict self-registration to `OPERATOR` role unconditionally; require explicit admin action for promotion | M1 | ORIGINAL_REQUEST §R1 |
| 2 | Environment & Secret Safety | Move admin credentials & secrets to env; block startup with default secrets in `ENVIRONMENT=production` | M1 | ORIGINAL_REQUEST §R1 |
| 3 | Private Key Remediation | Untrack `surakshanet-key.pem` from Git index, update `.gitignore`, provide standalone history rewrite script | M1 | ORIGINAL_REQUEST §R1 |
| 4 | CORS & HTTPS Redirection | Whitelist specific CORS origins with credentials; configure Nginx Port 80 301 redirect to HTTPS | M1 | ORIGINAL_REQUEST §R1 |
| 5 | Token Revocation & Logout | Add `jti` to JWT claims, implement Redis-backed token blacklist, and add `POST /api/v1/auth/logout` | M1 | ORIGINAL_REQUEST §R1 |
| 6 | Database Service Consolidation | Consolidate DB services to `timescaledb-ha:pg15`, enabling native PostGIS and TimescaleDB extensions | M2 | ORIGINAL_REQUEST §R2 |
| 7 | Alembic Versioned Migrations | Scaffold Alembic, replace silent `create_all`, and establish reproducible migration history | M2 | ORIGINAL_REQUEST §R2 |
| 8 | PostGIS Spatial Geometry | Replace raw lat/long JSON in `Junction` with PostGIS `Geometry('POINT', 4326)` and GIST spatial indexing | M2 | ORIGINAL_REQUEST §R2 |
| 9 | TimescaleDB Hypertables | Convert `traffic_readings` to TimescaleDB hypertable with composite PK `(id, timestamp)` & retention policy | M2 | ORIGINAL_REQUEST §R2 |
| 10 | Traffic Service Implementation | Complete `traffic_service.py` with real DB models, Pydantic v2 schemas, and bind to `api/traffic.py` | M2 | ORIGINAL_REQUEST §R2 |
| 11 | Standardized MQTT Topics & Tagging | Standardize topic namespaces in `shared/constants.py` and enforce `source: "live" \| "sim" \| "mock"` | M2 | ORIGINAL_REQUEST §R2 |
| 12 | Workload Decoupling | Offload long-running simulation & MARL training from web workers to dedicated background tasks | M3 | ORIGINAL_REQUEST §R3 |
| 13 | Redis Pub/Sub WebSocket Fanout | Unify WebSockets under `ConnectionManager` and broadcast cross-worker state via Redis pub/sub | M3 | ORIGINAL_REQUEST §R3 |
| 14 | Lazy-Loaded ML Models | Defer loading of YOLOv8, PyTorch, and XGBoost models to on-demand accessors rather than import time | M3 | ORIGINAL_REQUEST §R3 |
| 15 | Error Handling & Correlation ID | Add request tracking middleware (`X-Request-ID`) and standardize error responses to a structured envelope | M3 | ORIGINAL_REQUEST §R3 |
| 16 | Expanded Prometheus Metrics | Instrument active WebSocket connections, Redis pub/sub throughput, queue depth, and ML latency | M3 | ORIGINAL_REQUEST §R3 |
| 17 | SUMO Corridor Network & TraCI Fixes | Align 4-junction arterial (18 links) with TraCI phase strings; resolve coordinator API mismatches | M4 | ORIGINAL_REQUEST §R4 |
| 18 | Webster Fixed-Time Signal Control | Fix 18-character phase strings (`rrrrGGGggrrrrGGGgg`) in `webster_fallback.py` to prevent TraCI crashes | M4 | ORIGINAL_REQUEST §R4 |
| 19 | MARL TraCI In-Loop Training | Connect DQN agent to real SUMO TraCI environment instead of synthetic Gaussian noise | M4 | ORIGINAL_REQUEST §R4 |
| 20 | Reproducibility & Weight Versioning | Add deterministic random seeds (`torch`, `numpy`, `random`, SUMO), log hyperparameters, version weights | M4 | ORIGINAL_REQUEST §R4 |
| 21 | Topology-Derived Green-Wave | Replace hardcoded `return 0` with dynamic approach-phase mapping based on TraCI network topology | M4 | ORIGINAL_REQUEST §R4 |
| 22 | Empirical MARL vs Webster Study | Execute baseline study on identical corridor, recording >=10% delay/queue improvement in research artifact | M4 | ORIGINAL_REQUEST §R4 |
| 23 | Frontend Vitest & Store/UI Tests | Configure Vitest, RTL, jsdom, and create comprehensive test suites passing `npm test` | M5 | ORIGINAL_REQUEST §R5 |
| 24 | Strict TypeScript & OpenAPI Typing | Generate TypeScript types from OpenAPI schema, eliminate `any` in `api.ts`, `websocket.ts`, and pages | M5 | ORIGINAL_REQUEST §R5 |
| 25 | Route Code Splitting & Chunk Budget | Implement `React.lazy` and `Suspense` across 17 routes, split vendor chunks to keep all chunks <500 kB | M5 | ORIGINAL_REQUEST §R5 |
| 26 | WebSocket Reconnection & Origin UI | Add exponential backoff with jitter to WebSocket client; add visual `<TelemetrySourceBadge>` | M5 | ORIGINAL_REQUEST §R5 |
| 27 | Light Theme Commit & Error Boundary | Commit `design.md` light-theme modifications and implement React `<ErrorBoundary>` | M5 | ORIGINAL_REQUEST §R5 |
| 28 | Comprehensive CI Pipeline | Upgrade GitHub Actions CI to run `ruff`, `mypy`, `tsc`, Alembic migrations, backend/frontend tests | M6 | ORIGINAL_REQUEST §R6 |
| 29 | Deployment Smoke Checks | Implement automated smoke checks validating `/health`, `/metrics`, and WebSocket connectivity | M6 | ORIGINAL_REQUEST §R6 |
| 30 | Developer Tooling & Hygiene | Add `Makefile`, `.pre-commit-config.yaml`, validate `.env.example`, and include MIT `LICENSE` | M6 | ORIGINAL_REQUEST §R6 |
| 31 | Operations Runbook | Document architectural operations, deployment, and troubleshooting procedures in `README.md` | M6 | ORIGINAL_REQUEST §R6 |
| 32 | E2E Test Suite (Tiers 1-4) | Opaque-box requirement-driven test suite with >=11*N test cases covering all inventoried features | E2E | ORIGINAL_REQUEST Acceptance |
| 33 | Final E2E Pass & Coverage Hardening | Pass 100% of E2E tests, followed by Tier 5 white-box adversarial testing and forensic audit | M7 | ORIGINAL_REQUEST Acceptance |

---

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Track | Independent opaque-box test infrastructure and Tiers 1-4 test suite; publishes `TEST_READY.md` | none | DONE (TEST_READY.md published: 326 tests across Tiers 1-4) |
| M1 | Security Hardening & Secret Remediation | Features 1-5: Operator registration, env secrets, git key untrack & rewrite script, CORS/HTTPS, token revocation, conftest fix | none | DONE (Gate passed: 45/45 tests, 2x APPROVE, 2x APPROVE, CLEAN audit) |
| M2 | Data Integrity & Spatial Storage | Features 6-11: TimescaleDB consolidation, Alembic migrations, PostGIS geometry, hypertable, traffic_service, MQTT schemas | M1 | IN_PROGRESS (4f872f55-913e-45a9-b1cb-b6cfb8bb5198) |
| M3 | Architecture, Scalability & Observability | Features 12-16: Background task decoupling, Redis pub/sub WebSocket fanout, ML lazy loading, correlation ID, metrics | M2 | PLANNED |
| M4 | ML & Simulation Rigor | Features 17-22: SUMO TraCI repair, Webster 18-char fix, MARL real training, seeds, dynamic green wave, baseline study | M2, M3 | PLANNED |
| M5 | Frontend Quality & User Experience | Features 23-27: Vitest/RTL tests, OpenAPI types, code splitting <500kB, WebSocket backoff & badge, light theme commit, error boundary | M1, M3 | PLANNED |
| M6 | DevOps, Delivery & Documentation | Features 28-31: CI workflow (`ruff`, `mypy`, `tsc`, tests), smoke checks, Makefile, pre-commit, LICENSE, operations runbook | M1, M2, M5 | PLANNED |
| M7 | Final E2E Pass & Adversarial Hardening | Feature 33: Pass 100% of E2E test suite (Tiers 1-4), execute Tier 5 adversarial testing, Forensic Integrity Audit | E2E, M1-M6 | PLANNED |

---

## Interface Contracts

### 1. Authentication & Security (M1)
- `POST /api/v1/auth/register`: Takes `UserRegisterRequest`. Always creates user with `role = UserRole.OPERATOR`. Ignores email string patterns. Returns `UserResponse`.
- `PATCH /api/v1/users/{user_id}/role`: Requires authenticated `UserRole.ADMIN`. Updates role to validated enum.
- `POST /api/v1/auth/logout`: Requires Bearer token. Extracts `jti`, stores in Redis with TTL matching remaining token lifespan.
- `get_current_user`: Checks token `jti` against Redis blacklist. Raises 401 if revoked.
- `conftest.py`: Explicitly elevates test user to `UserRole.ADMIN` in DB to keep junction/admin tests passing.

### 2. Database & Spatial Storage (M2)
- Engine: `timescale/timescaledb-ha:pg15` on port 5432.
- `Junction.location`: `Geometry('POINT', srid=4326)` indexed with GiST. `latitude` and `longitude` kept as hybrid properties or synced columns.
- `TrafficReading`: Composite primary key `(id, timestamp)`. Configured via TimescaleDB hypertable `create_hypertable('traffic_readings', 'timestamp')` with chunk interval `1 day` and retention policy `90 days`.
- Alembic: Managed via `backend/alembic.ini` and `backend/alembic/versions/`. Initial migration creates tables, extensions (`postgis`, `timescaledb`), and hypertables.
- MQTT Topics: Defined in `shared/constants.py`:
  - `surakshanet/sensors/{sensor_id}/telemetry`
  - `surakshanet/junctions/{junction_id}/telemetry`
  - Payload MUST include: `{"source": "live" | "sim" | "mock", ...}`.

### 3. Architecture & WebSockets (M3)
- Redis Pub/Sub: Centralized in `app/core/redis.py` with singleton connection pool.
- WebSockets: All WebSocket connections register with `ConnectionManager`. Broadcasts publish to Redis channel `surakshanet:events:{channel}`. Worker listener receives Redis messages and dispatches to local client sockets.
- Correlation ID: Middleware inspects `X-Request-ID` or generates UUIDv4, attaches to `request.state.correlation_id` and response headers.
- Standardized Error Envelope: `{"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}`.
- Model Lazy Loading: Model loaders in `ml/` instantiated via cached getters (`get_vehicle_detector()`, `get_traffic_forecaster()`).

### 4. ML & Simulation (M4)
- SUMO TraCI: Network corridor links = 18. Signal phases = 18-character strings (`rrrrGGGggrrrrGGGgg`).
- Webster: Calculates split times based on lane flows and produces 18-character phase strings.
- Green Wave: `_get_approach_phase(from_junction, to_junction)` inspects TraCI network links to identify matching green phase index (0 for EW, 2 for NS).
- Baseline Study: Python runner script executes Webster and MARL on identical corridor seed scenarios. Outputs results table and metrics artifact (`ml/benchmarks/results/baseline_study_report.md` and JSON) verifying >=10% improvement in vehicle delay or queue length.

### 5. Frontend (M5)
- Bundle Budget: Single chunk size <= 500 kB. Vite `rollupOptions.output.manualChunks` separates vendor libraries (`vendor-react`, `vendor-maps`, `vendor-charts`).
- Route Splitting: `React.lazy()` for all route components in `App.tsx` wrapped with `<Suspense fallback={<LoadingSpinner />}>`.
- Testing: `npm test` runs Vitest with React Testing Library. Includes store tests and component tests.
- Telemetry Source Badge: Component displays `LIVE` (green), `SIM` (blue), or `MOCK` (amber) based on message `source` field.

---

## Code Layout
- `backend/app/`: FastAPI application code
  - `api/`: Route handlers
  - `core/`: Config, security, Redis client, database engine
  - `models/`: SQLAlchemy ORM models (with GeoAlchemy2 PostGIS)
  - `schemas/`: Pydantic schemas (Pydantic v2)
  - `services/`: Business logic (auth, traffic, MQTT consumer)
  - `middleware/`: Correlation ID, metrics, HTTPS redirection
- `backend/alembic/`: Database migration environment and versions
- `backend/tests/`: Pytest suite (all 41+ existing and new test cases)
- `frontend/dashboard/`: React 18 TypeScript Vite application
  - `src/components/`: Reusable UI components and `<ErrorBoundary>`
  - `src/pages/`: Route page components (code-split)
  - `src/services/`: API client and WebSocket client
  - `src/types/`: Generated OpenAPI types
  - `src/store/`: Zustand stores
- `simulation/`: SUMO networks, TraCI bridges, and environments
- `ml/`: MARL DQN, Webster controller, forecasters, green-wave preemption, and benchmark runners
- `shared/`: Shared schemas, constants, and MQTT definitions
- `infra/`: Docker Compose configurations, Nginx configs, and certificates
- `scripts/`: Operational scripts (history rewrite, smoke check)
- `tests/e2e/`: Opaque-box requirement-driven E2E test suite
