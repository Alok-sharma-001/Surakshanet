# 21 — Deployment & Operations

Covers **SN-018 … SN-022, SN-131**. Extends the existing `infra/` setup rather than replacing it.

---

## 1. Compose profiles

| Profile | File | Contents |
|---|---|---|
| `dev` | `infra/docker-compose.yml` (existing) | timescaledb, redis, mosquitto |
| `demo` | `infra/docker-compose.demo.yml` **NEW** | dev + backend, frontend, sumo-bridge, control-service, vision-worker, anomaly-service, prometheus, grafana |
| `prod` | `infra/docker-compose.prod.yml` (existing) | hardened, nginx TLS, no debug, secrets from env |

The demo profile is the one that must work flawlessly. Build it first; treat prod as reference.

---

## 2. Service definitions (demo profile)

| Service | Image/build | Ports | Depends on | Health check |
|---|---|---|---|---|
| `timescaledb` | timescale/timescaledb-ha:pg15 | 5432 | — | `pg_isready` |
| `redis` | redis:7-alpine | 6379 | — | `redis-cli ping` |
| `mosquitto` | eclipse-mosquitto:2 | 1883 | — | `mosquitto_sub -C 1 -t '$SYS/#' -W 2` |
| `backend` | `backend/Dockerfile` | 8000 | db, redis, mosquitto | `GET /health` |
| `sumo-bridge` | `simulation/Dockerfile` **NEW** | — | redis, backend | heartbeat key in Redis < 10 s old |
| `control-service` | `services/control_service/Dockerfile` **NEW** | — | redis, backend, sumo-bridge | last decision age < 15 s |
| `vision-worker` | `services/vision_worker/Dockerfile` **NEW** | — | redis, backend | `GET /vision/status` reachable |
| `anomaly-service` | `services/anomaly_service/Dockerfile` **NEW** | — | redis, backend | heartbeat < 30 s |
| `frontend` | `frontend/dashboard/Dockerfile` | 5173/80 | backend | `GET /` |
| `prometheus` | prom/prometheus | 9090 | — | `GET /-/healthy` |
| `grafana` | grafana/grafana | 3000 | prometheus | `GET /api/health` |

**Every image that runs SUMO code must contain the SUMO binaries and have `traci` importable** — the same defect as SN-013, one layer out. Verify in the image build, not at runtime.

---

## 3. `start.sh` (SN-018)

Ten steps, contract in [04-environment-setup.md §5](04-environment-setup.md). Additional operational requirements:

- Idempotent: running it twice does not duplicate containers or corrupt state.
- Every step logs to `logs/startup-$(date +%s).log` as well as stdout.
- Timeout per step (default 90 s) with the step name in the failure message.
- `--profile demo|dev` flag; demo is the default.
- `--no-frontend` for headless verification runs.
- Prints the seed it started with, so a rehearsal and a demo are visibly the same run.

`stop.sh` shuts down in reverse dependency order, releasing SUMO junctions to their base programs first. `reset.sh` drops and recreates the database, re-seeds (SN-134) and restores SUMO to step 0.

---

## 4. Operations runbook

| Task | Command |
|---|---|
| Start everything | `./start.sh` |
| Stop | `./stop.sh` |
| Reset to demo state | `./reset.sh` |
| Migrate | `make migrate` |
| Backup | `scripts/backup_db.sh` (existing) |
| Retention purge | `scripts/retention.sh` (SN-108) |
| Smoke check | `make smoke` |
| Critical tests | `make test-critical` |
| Determinism check | `make verify-determinism` |
| Tail control decisions | `docker logs -f surakshanet-control-service` |

---

## 5. Observability

Prometheus scrapes the backend (existing `metrics_middleware`) plus the new control-loop metrics from [08-marl-control.md §6](08-marl-control.md).

**Grafana dashboards to have ready** (they are also demo assets):
1. **Control loop** — decisions/min by controller, clamp rate by reason, inference latency, step lag.
2. **Corridor** — activations, clearance time, cross-street max red, recovery time.
3. **Incidents** — detections, confirmations, dismissals, false-positive rate.
4. **System** — API p95, WS connections, Redis pub/sub rate, DB size.

Dashboard 1 is worth showing to a judge who asks whether the control loop is really running.

---

## 6. Failure playbook (demo conditions)

| Symptom | First check | Action |
|---|---|---|
| Dashboard shows disconnected | `/health/deep` | restart the failing dependency; **do not** switch to any fallback that fabricates data |
| No control decisions | control-service logs | check telemetry channel name (SN-028) and weights load |
| SUMO not stepping | bridge logs | verify `traci` import and the TraCI port |
| Corridor stuck on green | corridor timeout guard | `POST /emergency/deactivate/{id}` releases and restores |
| A/B never completes | ab_runner logs | both arms must use the same seed; a mismatch is rejected by design |
| Numbers differ between rehearsals | seed | confirm `DEMO_SEED` reached every SUMO invocation |

**Rule under demo pressure:** if a subsystem is down, show the honest unavailable state and say so. That is a far better outcome than a fallback that invents numbers — which is the failure mode this entire project is correcting.
