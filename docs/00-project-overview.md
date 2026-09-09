# 00 — Project Overview & How To Use This Documentation

**Status:** Authoritative. This directory is the single source of truth for all remaining SurakshaNet development.
**Baseline:** The independent code audit of commit `84f8f6c` (2026-09-09). Completion measured at **~42%** against the full vision; target **8.5/10** hackathon project.
**Governing principle:** *Nothing in this project may claim an outcome it cannot measure.*

---

## 1. Who this document set is for

This is written to be handed to a developer or an AI coding agent with the instruction:

> "Follow this documentation from top to bottom. Inspect the existing repository before modifying anything. Implement every requirement, verify every milestone, and do not skip any unresolved item."

Every task carries a stable ID (`SN-001` … `SN-150`) defined in [`CHECKLIST.md`](CHECKLIST.md). Every document below references those IDs. **The checklist is the execution surface; these documents are the specification.**

---

## 2. The one-sentence problem statement

SurakshaNet has production-grade infrastructure (TimescaleDB + PostGIS, Redis pub/sub, MQTT, SUMO digital twin with working TraCI control) and real trained ML artifacts (YOLOv8n, LSTM+XGBoost, a DQN policy) — **but the intelligence layer is not connected to the control layer**, and several UI/API surfaces present fabricated values as if they were model output.

Everything in this roadmap follows from that sentence.

---

## 3. Non-negotiable engineering rules

These apply to every task in every phase. A change that violates one of these is rejected regardless of whether it "works".

| # | Rule | Rationale |
|---|---|---|
| R1 | **No fabricated values may reach an API response or the UI.** If a real value is unavailable, return an explicit unavailable state. | A judge who finds one invented number discredits the whole project. |
| R2 | **Every numeric value carries provenance** (`sumo` / `vision` / `mqtt` / `model` / `heuristic` / `manual`). | Distinguishes measurement from estimation. See [07-telemetry.md](07-telemetry.md). |
| R3 | **A heuristic value must never be styled like a measured or model value in the UI.** | Visual parity is an implicit claim. |
| R4 | **The AI may never bypass the signal safety envelope.** Min/max green, amber, all-red and pedestrian service are enforced *outside* the policy. | Safety credibility; see [08-marl-control.md](08-marl-control.md). |
| R5 | **No AI output may be phrased as a legal or medical determination.** Flags are `UNVERIFIED` until a human resolves them. | See [14-incident-detection.md](14-incident-detection.md). |
| R6 | **Camera-based drunk-driving detection is forbidden.** | Not physically possible; see [14-incident-detection.md §8](14-incident-detection.md). |
| R7 | **Every improvement percentage is computed from simulation output, never typed in.** | See [08-marl-control.md §9](08-marl-control.md). |
| R8 | **Documentation may not describe a feature as operational unless it is implemented, integrated, tested and demonstrable.** | See [23-final-acceptance.md](23-final-acceptance.md). |
| R9 | **Determinism:** every demo path runs from a fixed seed and produces reproducible numbers. | See [20-demo-scenarios.md](20-demo-scenarios.md). |
| R10 | **Do not add features outside this roadmap.** No new 3D/Three.js, no ANPR, no decorative UI. | Feature count is not the goal. |

---

## 4. Document map

| File | Covers | Primary phases |
|---|---|---|
| [00-project-overview.md](00-project-overview.md) | This file — index, rules, glossary | all |
| [01-current-state.md](01-current-state.md) | Subsystem-by-subsystem baseline: Current → Required → Gap → Tasks → Acceptance | all |
| [02-system-architecture.md](02-system-architecture.md) | Target architecture, service topology, end-to-end integration chain | all |
| [03-development-roadmap.md](03-development-roadmap.md) | **Phases 0–10 with exact tasks, gates and dependencies** | all |
| [04-environment-setup.md](04-environment-setup.md) | Python/venv/`traci` fix, dependency matrix, one-command startup, health checks | 1 |
| [05-database.md](05-database.md) | All schema changes, migrations, retention policies | 2–7 |
| [06-api-contracts.md](06-api-contracts.md) | Every endpoint: request, response, errors, auth, provenance | 2–7 |
| [07-telemetry.md](07-telemetry.md) | Canonical telemetry schema, Redis channels, MQTT topics, provenance contract | 2 |
| [08-marl-control.md](08-marl-control.md) | DQN control service, safety envelope, **A/B proof harness** | 2 |
| [09-dynamic-signals.md](09-dynamic-signals.md) | Signal state machine, inputs/outputs, edge cases | 2 |
| [10-emergency-corridor.md](10-emergency-corridor.md) | ETA propagation, plan capture/restore, cross-street protection | 3 |
| [11-event-management.md](11-event-management.md) | Event entity, what-if dual-world simulation, alternative routes | 4 |
| [12-citizen-advisory.md](12-citizen-advisory.md) | Public no-login advisory system | 4 |
| [13-computer-vision.md](13-computer-vision.md) | Real YOLO pipeline, tracking, PCU, wrong-way, no-parking, rash-driving flags | 5 |
| [14-incident-detection.md](14-incident-detection.md) | Anomaly-based incident detection, response state machine, drunk-driving policy | 6 |
| [15-routing.md](15-routing.md) | A* engine fed by live congestion, alternatives, VMS | 3–4 |
| [16-rbac.md](16-rbac.md) | 5 roles, full permission matrix | 7 |
| [17-security-privacy.md](17-security-privacy.md) | Blur-by-default, retention, governance, model limitations | 7 |
| [18-audit-logging.md](18-audit-logging.md) | Audit log schema and mandatory logged actions | 7 |
| [19-testing.md](19-testing.md) | Test rebuild: 15 critical paths, deletion of decorative tests | 8 |
| [20-demo-scenarios.md](20-demo-scenarios.md) | Scenarios A–E, deterministic configuration | 9 |
| [21-deployment.md](21-deployment.md) | Compose topology, service definitions, ops runbook | 1, 9 |
| [22-hackathon-demo.md](22-hackathon-demo.md) | Demo script, checklists, full judge Q&A | 9 |
| [23-final-acceptance.md](23-final-acceptance.md) | Definition of Done, final 5-condition completion matrix | 10 |
| [24-frontend.md](24-frontend.md) | Frontend consolidation, removal of client-side fake data | 2–6 |
| [CHECKLIST.md](CHECKLIST.md) | **Master checklist SN-001 … SN-150 with status tracking** | all |

---

## 5. Execution order (mandatory)

The order below is derived from the audit's priority ranking and **must not be reordered**, because later phases depend on earlier ones both technically and for credibility.

```
PHASE 0  Cleanup            — eliminate every fabricated output          (SN-001..012)
PHASE 1  Infrastructure     — traci fix, one-command startup, health     (SN-013..022)
PHASE 2  Real AI Control    — DQN → SUMO, safety envelope, A/B proof     (SN-023..038)
PHASE 3  Emergency Corridor — ETA propagation, restore, cross-street     (SN-039..050)
PHASE 4  Event + Citizen    — what-if simulation, public advisory        (SN-051..068)
PHASE 5  Computer Vision    — real pipeline, wrong-way, no-parking       (SN-069..082)
PHASE 6  Incident System    — anomaly detection, response state machine  (SN-083..096)
PHASE 7  Governance         — RBAC, audit, privacy, retention            (SN-097..110)
PHASE 8  Testing            — 15 real critical-path tests                (SN-111..126)
PHASE 9  Demo Hardening     — scenarios, determinism, backup video       (SN-127..138)
PHASE 10 Final Acceptance   — 5-condition matrix, doc truth pass         (SN-139..150)
```

**Phase gates are hard.** A phase is not started until the previous phase's completion gate in [03-development-roadmap.md](03-development-roadmap.md) passes.

---

## 6. Repository layout (current, verified)

```
surakshanet/
├── backend/app/
│   ├── api/            auth, users, traffic, junctions, ml, simulation,
│   │                   routing, alerts, emergency, signals, websocket_routes
│   ├── models/         user, junction (+TrafficSensor), traffic, signal, alert (+EmergencyEvent)
│   ├── schemas/        auth, traffic, ml, alert
│   ├── services/       auth_service, traffic_service, alert_service, mqtt_consumer
│   ├── middleware/      correlation, metrics
│   ├── websocket/      manager (Redis-backed multi-worker fanout)
│   ├── config.py       pydantic-settings; API_PREFIX=/api/v1
│   └── main.py         lifespan: init_db, MQTT consumer, redis_pubsub_bridge
├── ml/
│   ├── marl/           agent, coordinator, networks, replay_buffer,
│   │                   webster_fallback, train_marl, weights/marl_policy_downtown.pth
│   ├── vision/         vehicle_detector, pcu_engine, rtsp_stream_worker, yolov8n.pt
│   ├── forecasting/    traffic_forecaster, feature_engineering, train_forecaster, weights/
│   ├── routing/        routing_engine (A*)
│   └── emergency/      green_wave
├── simulation/
│   ├── networks/       corridor.{nod,edg,net,rou}.xml, corridor.sumocfg
│   ├── scenarios/      demand_profiles
│   ├── sumo_env.py     SumoEnvironment (TraCI wrapper)
│   ├── sumo_live_bridge.py  SUMO ⇄ Redis bridge
│   └── network_generator.py
├── shared/constants.py PCU_FACTORS, SIGNAL_CONSTRAINTS, MQTT topics
├── frontend/dashboard/ React 18 + TS + Vite + Zustand + Leaflet + Recharts
├── infra/              docker-compose.yml, nginx, mosquitto, prometheus, grafana
├── scripts/            backup_db.sh, purge_history.sh, smoke_check.sh
└── tests/              e2e (tier1/tier2/tier3) + backend/tests
```

**New top-level components introduced by this roadmap:**

```
services/
├── control_service/    NEW — DQN inference loop (Phase 2)
├── vision_worker/      NEW — video → detection → telemetry (Phase 5)
└── anomaly_service/    NEW — incident anomaly detection (Phase 6)
start.sh                NEW — one-command orchestrated startup (Phase 1)
```

---

## 7. Glossary

| Term | Meaning in this project |
|---|---|
| **PCU** | Passenger Car Unit. Weighted vehicle count using `shared/constants.py::PCU_FACTORS` (car 1.0, motorcycle 0.5, auto-rickshaw 1.0, bus/truck 3.0, bicycle 0.2, LCV 1.5). |
| **Provenance** | The `source` field on every value: `sumo` \| `vision` \| `mqtt` \| `model` \| `heuristic` \| `manual`. |
| **Safety envelope** | Hard constraints applied to every policy action *after* inference: min green, max green, amber, all-red, pedestrian service. |
| **Control step** | One decision cycle of the control service (default 5 simulation seconds). |
| **Green corridor** | Rolling signal pre-emption ahead of an emergency vehicle based on per-junction ETA. |
| **Dual-world simulation** | Two SUMO runs on identical seed/network/demand differing in exactly one variable (controller, or event injection). |
| **UNVERIFIED** | State of any AI-generated flag before a human operator confirms or dismisses it. |
| **A/B proof** | Measured comparison of Webster fixed-time vs DQN on identical demand, producing the project's headline number. |

---

## 8. What this project explicitly will NOT do

Recorded here so no agent adds them "to be helpful":

- Camera-based drunk-driving / intoxication detection (**forbidden**, see R6).
- ANPR / license-plate recognition enabled by default (blur-by-default instead).
- Any claim that the system controls real-world traffic hardware today.
- Additional Three.js / decorative 3D. `frontend/dashboard/src/components/Studio/` is frozen — no extensions.
- Growth of the E2E test file count for its own sake.
- Retraining the forecaster on real city data (no such dataset exists; synthetic provenance is declared instead).
