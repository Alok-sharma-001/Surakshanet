# Surakshanet — Production-Grade Roadmap

> [!IMPORTANT]
> **SUPERSEDED BY CANONICAL 10-PHASE ROADMAP**:
> This document is retained for historical audit context. The authoritative, execution-ready 10-phase development plan is located in [`docs/03-development-roadmap.md`](docs/03-development-roadmap.md) and tracked task-by-task in [`docs/CHECKLIST.md`](docs/CHECKLIST.md) (`SN-001` through `SN-150`).

**Goal:** Transform the current ITS MVP into a secure, scalable, defensible, production-ready system.

> Based on a full code audit of the repository. Each item is grounded in a specific file/line and is actionable. Suggested execution order is provided at the end.

---

## Table of Contents

1. [Phase 0 — Security Hardening (Do First)](#phase-0--security-hardening-do-first)
2. [Phase 1 — Data Integrity & Correctness](#phase-1--data-integrity--correctness)
3. [Phase 2 — Architecture & Scalability](#phase-2--architecture--scalability)
4. [Phase 3 — ML & Simulation Rigor](#phase-3--ml--simulation-rigor)
5. [Phase 4 — Frontend Quality](#phase-4--frontend-quality)
6. [Phase 5 — DevOps & Delivery](#phase-5--devops--delivery)
7. [Phase 6 — Docs & Polish](#phase-6--docs--polish)
8. [Suggested Execution Order](#suggested-execution-order)

---

## Phase 0 — Security Hardening (Do First)

> None of the other phases matter until the following are fixed.

### 0.1 — Public self-registration grants ADMIN 🚨
- **Where:** `backend/app/services/auth_service.py:120`
- **Problem:** `role = UserRole.ADMIN if "admin" in user_data.email.lower() else UserRole.OPERATOR`. `/auth/register` is unauthenticated, so anyone can register `anythingadmin@gmail.com` and become an administrator.
- **Fix:** Always assign `OPERATOR` on registration. Admin promotion only through an admin-only endpoint or a first-boot script that sets the initial admin explicitly.

### 0.2 — Hardcoded credentials in source 🚨
- **Where:** `backend/app/services/auth_service.py:144-149`
- **Problem:** Admin email/password (`aloks92440@gmail.com` / `Alok@2005`) are baked into `seed_default_admin()` and force-re-hashed on every boot.
- **Fix:** Load from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars; refuse to start in `ENVIRONMENT=production` if they are unset.

### 0.3 — Private keys & production secrets in the repo 🚨
- **Where:** `surakshanet-key.pem` (not in `.gitignore`), `infra/nginx/certs/fullchain.pem`, `infra/nginx/certs/privkey.pem`, `.env`, `.env.production`
- **Problem:** Private keys and production environment secrets are present in the working tree, and some may already be tracked in git history.
- **Fix:**
  - `git filter-repo` or BFG to purge from history.
  - Rotate **every** exposed secret (DB passwords, JWT secret, MQTT creds, SSH keys).
  - Add `infra/nginx/certs/` to `.gitignore`.
  - Wire DB / Redis / MQTT authentication + TLS in production.

### 0.4 — Infra exposed with default creds 🚨
- **Where:** `infra/docker-compose.yml`
- **Problem:** Postgres (`5434`), Redis (`6379`), MQTT (`1883`) are bound to all interfaces with `surakshanet_dev` credentials. Redis and MQTT have **no authentication at all**.
- **Fix:**
  - Bind services to `127.0.0.1` in dev.
  - Enable Redis `requirepass` and a Mosquitto password file in production.
  - Use a secrets manager in prod (docker secrets / SOPS / Doppler).

### 0.5 — JWT design gaps 🟠
- **Where:** `backend/app/config.py:25`, `backend/app/services/auth_service.py`
- **Problem:** Tokens cannot be revoked; refresh tokens are opaque and returned in the body; `JWT_SECRET_KEY` has a fallback default; `python-jose` is used (maintenance-mode library).
- **Fix:**
  - Enforce a non-default secret at startup.
  - Rotate refresh tokens on each use + add `jti` with a Redis denylist for revocation.
  - Serve refresh tokens as httpOnly cookies.
  - Consider migrating to `PyJWT` (actively maintained).

### 0.6 — CORS wildcard + credentials (invalid per spec) 🟠
- **Where:** `backend/app/config.py:30`, `backend/app/main.py:87-93`
- **Problem:** `CORS_ORIGINS=["*"]` with `allow_credentials=True` — browsers reject this combination.
- **Fix:** Explicit origin allowlist loaded from env in production.

### 0.7 — No brute-force protection on auth 🟠
- **Where:** `infra/nginx/nginx.conf` (only nginx rate limiting)
- **Problem:** Per-request rate limiting only; no per-account throttling, no lockout.
- **Fix:** Add in-app login throttling (Redis counters), lockout after N failures, and generic error messages to avoid user/enumeration leaks.

### 0.8 — HTTP port 80 serves the app without redirect 🟡
- **Where:** `infra/nginx/nginx.conf`
- **Problem:** The port-80 server proxies the app directly instead of redirecting to HTTPS.
- **Fix:** 301 redirect `server { listen 80; }` → 443 and add a real Content-Security-Policy header.

---

## Phase 1 — Data Integrity & Correctness

### 1.1 — Alembic migrations (currently missing)
- **Where:** repo-wide (`requirements.txt` lists `alembic` but there is no `migrations/` dir)
- **Problem:** `Base.metadata.create_all` in `app/database.py:30-36` silently swallows errors and there are no versioned schema migrations.
- **Fix:** Introduce Alembic, generate an initial migration, and replace `create_all`.

### 1.2 — Actually use PostGIS + TimescaleDB
- **Problem:** Both databases are deployed (`infra/docker-compose.yml`) but never used to their potential.
- **Fixes:**
  - `Junction.geometry` is a `JSON` column (`app/models/junction.py:29`) → switch to `geometry(Point, 4326)` with an index for `ST_DWithin` spatial queries (routing engine).
  - `TrafficReading` is a plain table (`app/models/traffic.py`) → create a TimescaleDB **hypertable** on `timestamp` with a retention policy in the migration.
  - Enable the `postgis` extension at init (currently `init_db` silently prints the failure).

### 1.3 — Finish `traffic_service.py`
- **Where:** `backend/app/services/traffic_service.py`
- **Problem:** It is still a scaffold (`class Junction: pass`, `data.dict()` which was removed in Pydantic v2) and never imports the real models. The API duplicates query logic inline in `app/api/traffic.py`.
- **Fix:** Implement against the real SQLAlchemy models and schemas, or delete the dead file.

### 1.4 — Unify MQTT topic convention
- **Where:** `iot/simulator/mqtt_subscriber.py`, `backend/app/services/mqtt_consumer.py`, `iot/edge/signal_controller_bridge.py`
- **Problem:** Three different namespaces exist:
  - `surakshanet/junction/+/telemetry`
  - `surakshanet/sensors/+/telemetry`
  - `surakshanet/junctions/+/control`
- **Fix:** Define one canonical topic set in `shared/constants.py` and use it everywhere.

### 1.5 — Tag real vs. synthesized data
- **Where:** `mqtt_consumer._live_telemetry_loop`, `simulation.py` `MicroSimRunner`, `ml.py` `_training_status`
- **Problem:** The backend **fabricates** telemetry, simulation state, and training metrics when real sources are unavailable. Operators can't distinguish real from mock.
- **Fix:** Tag every event/record with `source: "sim" | "mock" | "live"` and surface that on the dashboard.

---

## Phase 2 — Architecture & Scalability

### 2.1 — Kill global mutable state in API workers
- **Where:** `backend/app/api/simulation.py`
- **Problem:** `sim_instance` and `active_websockets` are module globals. With `--workers 2`, each worker has its own copy and clients hit random workers.
- **Fix:** Run the simulation in a dedicated process that talks to the API via Redis (the pattern already exists in `simulation/sumo_live_bridge.py`). Deprecate `MicroSimRunner` from the API. Use Celery (already in `requirements.txt`) for ML training, image inference, and RTSP processing.

### 2.2 — Cross-worker WebSocket fan-out
- **Where:** `backend/app/websocket/manager.py`
- **Problem:** `ConnectionManager` is in-process only; broadcasts from one worker never reach clients connected to another.
- **Fix:** Route all WS broadcasts through the Redis pub/sub bridge (already implemented in `app/main.py`). Standardize on `manager.broadcast` — `simulation.py` hand-rolls its own `broadcast_state`.

### 2.3 — Lazy-load ML models
- **Where:** `backend/app/api/ml.py:35`
- **Problem:** YOLOv8 + LSTM models are instantiated at import time in every worker.
- **Fix:** Load on demand with `lru_cache`, or run inference in a Celery worker to cut startup time and RAM.

### 2.4 — Backend structure & consistency
- **Where:** `backend/app/`
- **Problem:** 6+ copy-pasted `try: redis = aioredis.from_url(...) / publish / aclose` blocks; inconsistent error bodies; no structured logging or request-ID chain.
- **Fix:** Add a `core` layer with:
  - A shared Redis publisher helper.
  - Exception handlers producing `{code, detail, request_id}`.
  - Structured logging middleware.

### 2.5 — Observability gap
- **Where:** `backend/app/middleware/metrics.py`, `infra/prometheus/prometheus.yml`
- **Problem:** Prometheus scrapes only HTTP request counters.
- **Fix:** Add gauges/histograms for:
  - WS connection count per channel (`manager.get_connection_count` already exists)
  - Redis pub/sub lag, MQTT message rate, simulation step rate
  - Model inference latency, DB pool size
- Ship a Grafana dashboard JSON with alert rules (scrape target: `surakshanet-backend`).

---

## Phase 3 — ML & Simulation Rigor

### 3.1 — Honest training API
- **Where:** `backend/app/api/ml.py` (`run_marl_training_task`)
- **Problem:** `/ml/train/start` caps at `min(episodes + 1, 20)` yet returns the user's requested episode count (e.g., 500). The training status payload is canned.
- **Fix:** Either run real training (in Celery) or rename to "simulated run" and return the real cap + source tag.

### 3.2 — MARL vs. Webster baseline study ⭐ (highest impact)
- **Where:** `ml/marl/` + `ml/marl/webster_fallback.py`
- **Problem:** No evidence that DQN beats the fixed-time baseline.
- **Fix:** Run a controlled experiment on the same SUMO corridor:
  - Baseline (Webster / actuated) vs. DQN policy.
  - Report delay, throughput, and LOS deltas.
- This single artifact turns a convincing demo into a defensible research-grade system.

### 3.3 — Reproducibility
- **Where:** `ml/marl/train_marl.py`, `ml/forecasting/train_forecaster.py`
- **Problem:** No fixed seeds, no logged hyperparameters, no artifact versioning.
- **Fix:** Set seed for Python/numpy/torch/SUMO `--seed`; log hyperparameters + data hash to MLflow/W&B; version model weights (`ml/marl/weights/*.pth`, `ml/forecasting/weights/*`).

### 3.4 — Real retraining loop
- **Where:** `ml/forecasting/traffic_forecaster.py` (`generate_synthetic_data`)
- **Problem:** Forecast weights were trained on synthetic data.
- **Fix:** Add a scheduled job: pull real `traffic_readings` from TimescaleDB → retrain → validate → promote weights if improved.

### 3.5 — Complete green-wave phase mapping
- **Where:** `ml/emergency/green_wave.py` (`_get_approach_phase`)
- **Problem:** Hardcodes `return 0` (placeholder).
- **Fix:** Derive approach→phase mapping from the SUMO `net.xml` topology (edge index per approach).

### 3.6 — SUMO bridge robustness
- **Where:** `simulation/sumo_live_bridge.py`
- **Problem:** Hand-rolled raw TCP RESP protocol for Redis (clever, but fragile); unauthenticated; no health reporting.
- **Fix:** Use `redis-py` inside the bridge container; add reconnection backoff and report health/lag to `/metrics`.

---

## Phase 4 — Frontend Quality

### 4.1 — Zero JavaScript tests
- **Where:** `frontend/dashboard/package.json`
- **Problem:** Only a `lint` script exists (no eslint config file), no Vitest/RTL/Playwright.
- **Fix:** Add Vitest + React Testing Library for stores/components and Playwright for the E2E simulation→dashboard loop. Wire `npm test` and `npm run lint` into CI.

### 4.2 — Kill the `any` types
- **Where:** `frontend/dashboard/src/services/api.ts`, `src/store/`
- **Fix:** Generate TypeScript types from the FastAPI OpenAPI schema (e.g., `openapi-typescript` on `/openapi.json`) and use them across the client.

### 4.3 — Route-level code splitting
- **Where:** `frontend/dashboard/src/App.tsx`
- **Problem:** All 20+ pages are imported eagerly into one bundle.
- **Fix:** Use `React.lazy` + `Suspense` per route.

### 4.4 — WebSocket hardening
- **Where:** `frontend/dashboard/src/services/websocket.ts`
- **Problem:** Fixed 2s reconnect, no cap/backoff/jitter, no "live vs sim" badge.
- **Fix:** Exponential backoff with jitter + reconnect cap; surface `source` field (ties to item 1.5).

### 4.5 — Stop hardcoding dev port detection
- **Where:** `frontend/dashboard/src/services/websocket.ts` (`window.location.port === '5173'`)
- **Fix:** Use Vite env (`import.meta.env.VITE_API_URL`).

### 4.6 — A11y + error boundaries
- **Where:** `frontend/dashboard/src/App.tsx`, `src/pages/`
- **Fix:** Add per-route error boundaries, loading skeletons, and an accessibility pass (keyboard nav, ARIA on signal controls and the emergency modal).

---
## Phase 5 — DevOps & Delivery

### 5.1 — Upgrade the CI pipeline
- **Where:** `.github/workflows/ci.yml`
- **Problem:** CI uses plain Postgres (PostGIS functions will fail), doesn't publish images, doesn't run migrations, has no coverage gate, no Python linting beyond flake8.
- **Fix:** Add `ruff` + `mypy`, use a PostGIS/TimescaleDB service, run Alembic migrations, upload coverage artifacts, enforce coverage thresholds.

### 5.2 — Harden the deployment pipeline
- **Where:** `.github/workflows/deploy.yml`
- **Problem:** No tests, no staging, no rollback, no post-deploy smoke checks.
- **Fix:** CI→CD gate → staging env → `docker compose up -d --wait` → smoke test `/health`, `/metrics`, and one WebSocket connect → rollback step.

### 5.3 — Developer experience
- **Where:** repo root
- **Fix:** Add `Makefile`/`justfile` (`up`, `down`, `logs`, `test`, `seed`), `pre-commit` hooks (ruff, tsc, gitleaks secret scan), and validate `.env.example` against `pydantic-settings`.

### 5.4 — Database backups
- **Where:** `infra/docker-compose.yml` (named volumes only)
- **Fix:** Add `pg_dump` / `pg_dump --timescaledb` cron jobs or `wal-g`; restore drills; volume snapshots.

### 5.5 — Image diet
- **Where:** `backend/Dockerfile`
- **Problem:** Installs full torch + ultralytics (~several GB per image).
- **Fix:** Keep the CPU-only torch index (already done), move `yolov8n.pt` + model weights to a cached mount or object storage, and consider `DockerSlim`.

---

## Phase 6 — Docs & Polish

### 6.1 — README upgrade
- **Problem:** `README.md` is minimal.
- **Fix:** Add architecture diagram (Mermaid), data-flow walkthrough, runbook (emergency override, MARL training, SUMO bring-up), env-var matrix, and API quickstart.

### 6.2 — Add missing docs
- **Fix:** Add `CONTRIBUTING.md`, a `docs/` folder for the research defense material (currently in `supporting docs/`), and a `STATUS.md` that honestly labels all simulated/mock production paths.

### 6.3 — License & hygiene
- **Problem:** License declared MIT in README but no `LICENSE` file exists.
- **Fix:** Add `LICENSE`, commit `design.md` and the currently modified frontend files.

### 6.4 — Repo hygiene
- **Fix:** Remove/gitignore `Travel/` screenshots and `surakshanet-key.pem`; exclude SUMO network assets from container image builds.

---

## Suggested Execution Order

```
Phase 0  Security (items 0.1–0.4 first)
   |
   v
Phase 1  Data integrity & migrations (1.x)
   |
   v
Phase 2  Architecture (2.x)  --  Phase 3  ML baseline study (3.2)  [parallel]
   |
   v
Phase 4  Frontend tests & types (4.x)
   |
   v
Phase 5  CI/CD upgrades (5.x)
   |
   v
Phase 6  Docs & polish (6.x)
```

### Quick wins (first bite -- all small, safe, high-value)

1. **0.1 / 0.2** — Remove the "admin-by-email" heuristic; move default admin credentials to env vars with a hard failure in production.
2. **1.1** — Scaffold Alembic and commit the initial migration.
3. **1.5** — Add a `source` field to synthetic telemetry/simulation events.
4. **3.2** — Run the MARL-vs-Webster baseline study and publish the result in the repo.

---

> **The single biggest credibility upgrade for this project:** the MARL-vs-Webster baseline study (3.2) + a Grafana operations dashboard (2.5) + the security fixes in Phase 0. That combination turns a convincing demo into a defensible, production-ready research system.
