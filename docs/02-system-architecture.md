# 02 — Target System Architecture

Describes the architecture **after** this roadmap is complete. Additions to the current system are marked **NEW**; everything else exists and must not be restructured.

---

## 1. Service topology

```
┌──────────────────────── PERCEPTION / SOURCES ─────────────────────────┐
│  SUMO (sumo-gui | sumo)          Vision Worker [NEW]      IoT / MQTT  │
│  4 signalised junctions J0-J3    demo.mp4 → YOLOv8n       edge devices│
│  lane-area detectors             → tracker → PCU          simulators  │
└──────────┬─────────────────────────────┬────────────────────┬─────────┘
           │ TraCI                       │                    │ MQTT 1883
           ▼                             ▼                    ▼
┌──────────────────────────────────────────────────────────────────────┐
│  SUMO Live Bridge          canonical telemetry (07-telemetry.md)     │
│  simulation/sumo_live_bridge.py    ── all producers emit ONE schema ──│
└──────────┬───────────────────────────────────────────────────────────┘
           │ PUBLISH traffic_updates
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                        REDIS  (pub/sub + cache)                      │
│  traffic_updates · control_commands[NEW] · control_decisions[NEW]    │
│  signal_events · emergency_events · alert_events · simulation_updates│
│  incident_events[NEW] · event_events[NEW] · advisory_events[NEW]     │
│  cv_detections[NEW]           + JWT denylist, rate limits            │
└───┬──────────────────┬───────────────────┬──────────────────┬────────┘
    │                  │                   │                  │
    ▼                  ▼                   ▼                  ▼
┌─────────────┐ ┌──────────────┐ ┌──────────────────┐ ┌───────────────┐
│  CONTROL    │ │  ANOMALY     │ │  FASTAPI BACKEND │ │  A/B RUNNER   │
│  SERVICE    │ │  SERVICE     │ │  (stateless)     │ │  [NEW]        │
│  [NEW]      │ │  [NEW]       │ │                  │ │  2× SUMO      │
│  DQN policy │ │  5 indicators│ │  REST + WS       │ │  same seed    │
│  + Webster  │ │  → incidents │ │  RBAC · audit    │ │  Webster vs   │
│  + SAFETY   │ │  UNVERIFIED  │ │  provenance      │ │  DQN          │
│  ENVELOPE   │ │              │ │                  │ │               │
└──────┬──────┘ └──────┬───────┘ └────────┬─────────┘ └───────┬───────┘
       │ TraCI         │                  │                    │
       ▼               ▼                  ▼                    ▼
   SUMO signals   incidents tbl   ┌──────────────────────────────────┐
                                  │  TIMESCALEDB + POSTGIS           │
                                  │  junctions · traffic_readings(HT)│
                                  │  signal_plans · alerts           │
                                  │  emergency_events · events[NEW]  │
                                  │  incidents[NEW] · advisories[NEW]│
                                  │  audit_logs[NEW] · control_      │
                                  │  decisions[NEW] · ab_runs[NEW]   │
                                  └──────────────────────────────────┘
                                                │
                                   ┌────────────┴────────────┐
                                   ▼                         ▼
                        ┌────────────────────┐   ┌────────────────────┐
                        │ OPERATOR FRONTEND  │   │ CITIZEN VIEW [NEW] │
                        │ /app/*  (auth)     │   │ /public (no auth)  │
                        │ command centre     │   │ 3-second read      │
                        └────────────────────┘   └────────────────────┘
```

---

## 2. Processes and their contracts

| Process | Entry point | Language/runtime | Reads | Writes | Restart policy |
|---|---|---|---|---|---|
| Backend API | `backend/app/main.py` | uvicorn, 2 workers | Postgres, Redis | Postgres, Redis | always |
| SUMO bridge | `simulation/sumo_live_bridge.py` | python + traci | SUMO via TraCI, Redis `control_commands` | Redis `traffic_updates`, TraCI setters | on-failure |
| **Control service** | `services/control_service/main.py` **NEW** | python + torch | Redis `traffic_updates`, policy weights | Redis `control_commands`, `control_decisions`; Postgres `control_decisions` | always |
| **Vision worker** | `services/vision_worker/main.py` **NEW** | python + ultralytics | video file / RTSP | Redis `traffic_updates` (`source=vision`), `cv_detections` | on-failure |
| **Anomaly service** | `services/anomaly_service/main.py` **NEW** | python | Redis `traffic_updates` | Redis `incident_events`; Postgres `incidents` | always |
| **A/B runner** | `services/control_service/ab_runner.py` **NEW** | python + traci | scenario config | Postgres `ab_runs`; Redis `simulation_updates` | on-demand |
| Frontend | `frontend/dashboard` (vite/nginx) | node/nginx | Backend REST + WS | — | always |

**Rule:** the control service is the *only* process permitted to issue signal-phase commands during adaptive operation. The bridge executes commands; it does not originate them. The hardcoded optimisation publisher at `sumo_live_bridge.py:296–307` is deleted in SN-002.

---

## 3. End-to-end integration chain (Part 24 requirement)

Every link below must be demonstrable in a running system. No feature may remain isolated.

| # | Stage | Implemented by | Verified by |
|---|---|---|---|
| 1 | Traffic data | SUMO detectors / MQTT / video frames | SN-114, SN-115 |
| 2 | AI perception | Vision worker: YOLOv8n → tracker → class → PCU | SN-121 |
| 3 | Traffic state | Canonical telemetry → `traffic_readings` + Redis | SN-114 |
| 4 | Prediction | LSTM+XGBoost forecaster (`source=model`, synthetic-trained, declared) | SN-036 |
| 5 | Signal optimisation | Control service: state → DQN → safety envelope → TraCI | SN-116, SN-117 |
| 6 | Emergency response | Corridor: A* route → per-junction ETA → rolling pre-emption → restore | SN-118 |
| 7 | Event simulation | Dual-world SUMO what-if → per-link deltas → severity | SN-119 |
| 8 | Route recommendation | A* alternatives on live weights → ranked routes | SN-063 |
| 9 | Operator decision | Approve diversion / confirm incident (human gates) | SN-122 |
| 10 | Citizen advisory | Advisory generated from approved decision → `/public` | SN-120 |
| 11 | Incident response | Anomaly → UNVERIFIED → operator → reroute + warning | SN-122 |
| 12 | Analytics | A/B results, corridor recovery, incident stats | SN-125 |
| 13 | Audit | Every step above writes an `audit_logs` row | SN-124 |

**Acceptance for the chain (SN-146):** one continuous run of Scenario E exercises stages 1→13 and each stage is evidenced by a database row or a Redis message captured in the test log.

---

## 4. Control-plane data flow (the audit's central fix)

```
 SUMO lane-area detectors
   │  queue, speed, occupancy, accumulated wait, phase, elapsed green
   ▼
 sumo_live_bridge  ── canonical telemetry ──▶  Redis: traffic_updates
                                                   │
                                                   ▼
                                        CONTROL SERVICE  (every 5 sim-seconds)
                                          1. aggregate telemetry per junction
                                          2. build 8-dim state vector
                                          3. mode? MARL → DQN.select_action(greedy)
                                                    WEBSTER → Webster plan
                                                    MANUAL → operator command only
                                          4. SAFETY ENVELOPE (hard clamp)
                                          5. emit command
                                                   │
                                                   ▼
                                        Redis: control_commands
                                                   │
                                                   ▼
                                        sumo_live_bridge → traci.trafficlight.*
                                                   │
                                                   ▼
                                            new traffic state
                                                   │
                                       reward computed, decision persisted
                                                   ▼
                              Postgres control_decisions  +  Redis control_decisions
                                                   ▼
                                        WebSocket /ws/control → UI
```

Full specification in [08-marl-control.md](08-marl-control.md).

---

## 5. Configuration and constants

All shared names live in one place. **No literal channel name, topic string, PCU factor or signal constraint may be duplicated in a service.**

| Concern | Single source |
|---|---|
| PCU factors | `shared/constants.py::PCU_FACTORS` |
| Signal constraints | `shared/constants.py::SIGNAL_CONSTRAINTS` |
| MQTT topics | `shared/constants.py::MQTT_*_TOPIC` |
| Redis channels | `shared/constants.py::REDIS_CHANNELS` **NEW (SN-028)** |
| Provenance enum | `shared/constants.py::DataSource` **NEW (SN-008)** |
| Telemetry schema | `shared/telemetry.py` **NEW (SN-023)** |
| Demo seed | `shared/constants.py::DEMO_SEED = 42` **NEW (SN-127)** |

---

## 6. Failure behaviour (mandatory, R1)

| Failure | Required behaviour | Forbidden behaviour |
|---|---|---|
| SUMO / TraCI unavailable | `503 {"status":"simulation_unavailable","reason":...}`; UI shows "Simulation unavailable" | Any synthetic traffic numbers (`MicroSimRunner` deleted, SN-005) |
| DQN weights missing | Control service refuses `MARL` mode, falls back to `WEBSTER`, logs and surfaces `controller: "webster (marl weights unavailable)"` | Silently pretending MARL is active |
| Forecaster weights missing | `source: "heuristic"`, **no confidence field** | `confidence: 0.92` on a heuristic (SN-006) |
| Vision worker stopped | CV panel shows "no video source" | Animated boxes (SN-004) |
| Redis down | Backend returns 503 on affected routes; WS clients show disconnected | Frontend-generated telemetry (SN-119) |
| Backend down | Frontend shows disconnected state on every data panel | Client-side simulation engine continuing to move numbers |

---

## 7. Deployment profiles

| Profile | Compose file | Contents | Use |
|---|---|---|---|
| `dev` | `infra/docker-compose.yml` | infra + backend + frontend hot reload | development |
| `demo` | `infra/docker-compose.demo.yml` **NEW** | full stack + control service + vision worker + anomaly service, fixed seed, sample data seeded | **hackathon demo** |
| `prod` | `infra/docker-compose.prod.yml` | hardened, nginx TLS, no debug | reference only |

Details in [21-deployment.md](21-deployment.md).
