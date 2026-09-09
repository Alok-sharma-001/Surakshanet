# 04 — Environment Setup & One-Command Startup

Covers **SN-013 … SN-022**. The `traci` defect (SN-013) is the highest-priority environment fix in the project: `import traci` currently succeeds under `/usr/bin/python3` but **fails inside `.venv`**, and `simulation/sumo_live_bridge.py` calls `sys.exit(1)` when it cannot import — a guaranteed live-demo failure.

---

## 1. Verified dependency matrix

| Component | Required version | Verify with | Current status |
|---|---|---|---|
| Python | 3.11+ (repo shows 3.11/3.13/3.14 pycache — standardise on **3.11**) | `python --version` | mixed — standardise (SN-017) |
| Eclipse SUMO | 1.19+ | `sumo --version` | installed at `/usr/bin/sumo` |
| `traci` | matching SUMO | `python -c "import traci"` | **FAILS in `.venv`** (SN-013) |
| `libsumo` | optional, faster | `python -c "import libsumo"` | optional |
| PostgreSQL | 15 + TimescaleDB 2.x + PostGIS 3.x | `docker exec surakshanet-timescaledb psql -c "\dx"` | present |
| Redis | 7.x | `redis-cli ping` | present |
| Mosquitto | 2.x with password file | `mosquitto_sub -h localhost -t '#' -u ...` | present |
| Node | 20 LTS | `node --version` | present |
| PyTorch | 2.x (CPU is sufficient) | `python -c "import torch"` | present |
| ultralytics | 8.x | `python -c "import ultralytics"` | present |

---

## 2. SN-013 — Fixing `traci` in the virtualenv

**Why it matters:** the backend, the SUMO bridge and the new control service must all run from the same interpreter as the one that can talk to SUMO. Today they cannot.

**Option A (preferred) — install into the venv:**
```bash
source .venv/bin/activate
pip install eclipse-sumo traci sumolib
python -c "import traci, sumolib; print(traci.__file__)"
```

**Option B — recreate the venv with system packages visible:**
```bash
deactivate 2>/dev/null || true
mv .venv .venv.bak
python3.11 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
python -c "import traci; print(traci.__file__)"
```

**Option C — explicit path injection (fallback only):** keep the `SUMO_HOME/tools` insertion already present at `simulation/sumo_live_bridge.py:29–38` but **also** add it to `simulation/sumo_env.py` and the control service, and set `SUMO_HOME=/usr/share/sumo` in `.env`.

**Pin the result (SN-017)** in `requirements.txt`:
```
eclipse-sumo==1.19.0
traci==1.19.0
sumolib==1.19.0
```

**Import guard (SN-016)** — add to backend startup, the bridge, and the control service:
```python
try:
    import traci  # noqa: F401
except ImportError as exc:
    raise SystemExit(
        "FATAL: 'traci' is not importable from this interpreter.\n"
        f"  interpreter: {sys.executable}\n"
        "  fix: see docs/04-environment-setup.md §2 (SN-013)"
    ) from exc
```
The guard must name the interpreter and point at this document. A silent fallback is forbidden.

---

## 3. SN-014 / SN-127 — Determinism

Add to `shared/constants.py`:
```python
DEMO_SEED: int = 42
```
Every SUMO invocation must pass `--seed ${DEMO_SEED}` and `--random false`. Apply in `simulation/sumo_env.py::start` (command assembly) and in `simulation/networks/corridor.sumocfg`.

**Verification:** run the same scenario twice and diff the metric series — they must be identical. This is the acceptance test for SN-142.

---

## 4. SN-015 — Lane-area detectors

The 8-dim DQN state needs per-approach queue, speed, occupancy and accumulated wait. Create `simulation/networks/corridor.det.xml` with one `<laneAreaDetector>` per approach lane of `J0..J3` (4 junctions × 4 approaches), then reference it from `corridor.sumocfg` under `<additional-files>`.

Detector IDs follow `det_{junction}_{direction}_{lane}` — e.g. `det_J1_N_0`. The state builder (SN-034) parses direction from this convention; do not deviate from it.

---

## 5. SN-018 — `start.sh` contract

`./start.sh` must perform exactly these ten steps, in order, and **fail loudly with a named cause** at any step:

```
1.  Check dependencies      docker, python, node, sumo, traci import, .env present
2.  Start infrastructure    docker compose -f infra/docker-compose.demo.yml up -d
                            timescaledb, redis, mosquitto
3.  Wait for health         poll each container's healthcheck, 60s timeout each
4.  Start backend           alembic upgrade head, then uvicorn; wait for /health
5.  Start SUMO bridge       simulation/sumo_live_bridge.py --seed $DEMO_SEED
6.  Start control service   services/control_service/main.py
7.  Start frontend          vite (dev) or nginx (demo)
8.  Verify all services     GET /health/deep must return every dependency healthy
9.  Print URLs              dashboard, public view, API docs, Grafana, Prometheus
10. Exit 0                  or exit non-zero with the failing step and reason
```

**Required output on failure** (example):
```
[4/10] Backend .............................. FAILED
       cause: alembic upgrade head exited 1
       detail: connection refused to timescaledb:5432
       fix:    docs/04-environment-setup.md §7 (database not ready)
```

**Required output on success:**
```
SurakshaNet is up.
  Operator dashboard  http://localhost:5173/app
  Citizen view        http://localhost:5173/public
  API docs            http://localhost:8000/docs
  Grafana             http://localhost:3000
  Seed                42  (deterministic)
```

Companion scripts: `stop.sh` (graceful shutdown, reverse order) and `reset.sh` (drop + recreate DB, re-seed demo data, restore SUMO to step 0) — **SN-021**.

---

## 6. SN-019 — Health endpoints

`GET /health` — liveness only:
```json
{"status": "ok", "version": "1.0.0"}
```

`GET /health/deep` — readiness with per-dependency detail. **Every field is measured, never assumed:**
```json
{
  "status": "degraded",
  "checked_at": "2026-09-09T12:00:00Z",
  "dependencies": {
    "postgres":        {"status": "ok",          "latency_ms": 3},
    "redis":           {"status": "ok",          "latency_ms": 1},
    "mqtt":            {"status": "ok"},
    "sumo":            {"status": "ok",          "step": 1420},
    "traci":           {"status": "ok",          "module": "/usr/share/sumo/tools/traci/__init__.py"},
    "control_service": {"status": "ok",          "last_decision_age_s": 3},
    "vision_worker":   {"status": "unavailable", "reason": "no video source configured"},
    "marl_weights":    {"status": "ok",          "path": "ml/marl/weights/marl_policy_downtown.pth"},
    "forecast_weights":{"status": "ok",          "training_data": "synthetic"}
  }
}
```
`status` is `ok` only when every dependency is `ok`; otherwise `degraded`, and the UI header reflects it. **`vision_worker: unavailable` is a correct, honest state — not a failure to hide.**

---

## 7. Common failures and their causes

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'traci'` | venv lacks SUMO python bindings | §2, SN-013 |
| Bridge exits immediately, no message | `sys.exit(1)` on import failure | SN-016 import guard |
| Metrics differ between identical runs | seed not passed | §3, SN-014 |
| `alembic upgrade head` connection refused | DB not healthy yet | step 3 health wait, SN-018 |
| Control service idles, no decisions | telemetry channel name mismatch | SN-028 single-source channels |
| WebSocket connects then drops | nginx missing upgrade headers | `infra/nginx/` config |
| Empty dashboard, no error | frontend fell back to local data | must not exist after SN-119 |
