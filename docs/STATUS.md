# Surakshanet Subsystem & Production Status Matrix

> [!IMPORTANT]
> **SUPERSEDED BY AUDITED CODEBASE BASELINE**:
> The definitive source-level status for all 34 subsystems is maintained in [`docs/01-current-state.md`](docs/01-current-state.md).
> The mandatory data provenance contract (`DataSource`: `sumo`, `vision`, `mqtt`, `model`, `heuristic`, `manual`) is specified in [`docs/07-telemetry.md`](docs/07-telemetry.md).

This document provides historical context on subsystem integration paths and legacy tagging.

---

## Telemetry Source Tagging Contract

Every packet, WebSocket frame, and database reading in Surakshanet is strictly tagged with an origin metadata tag:

| Tag | Meaning | Dashboard Indicator | Trigger Condition |
| :--- | :--- | :--- | :--- |
| `live` | Real-time physical IoT hardware or edge camera feed | Green / Emerald badge | IoT MQTT broker ingress from physical controller cabinet or camera worker |
| `sim` | Physics-based TraCI SUMO micro-simulation corridor | Blue / Sky badge | Background simulation daemon running `simulation/sumo_env.py` |
| `mock` | Synthetic fallback generator | Amber / Yellow badge | Fallback active when both live hardware and TraCI binary are offline |

---

## Subsystem Implementation Matrix

| Subsystem | Primary Engine | Fallback Mode | Production Status | Defense Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Spatial Junction Master** | PostgreSQL 15 + PostGIS (`ST_DWithin`, `ST_MakeEnvelope`) | In-memory spatial radius | **PRODUCTION-READY** | Consolidated under `timescale/timescaledb-ha:pg15` with GiST spatial indexing. |
| **Sensor Telemetry Storage** | TimescaleDB Hypertables (7-day chunk partition) | Plain relational table | **PRODUCTION-READY** | Hypertable compression enabled with automated retention policies. |
| **Adaptive Signal Control** | Multi-Agent Reinforcement Learning (DQN, 18-link corridor) | Webster Fixed-Time Signal Plan (18-char phase) | **RESEARCH-GRADE** | Dynamic multi-agent control evaluated against Webster fixed-time baseline via live `ab_runs` harness. |
| **Emergency Preemption** | Dynamic Topology Green-Wave Engine | Manual Phase Hold Override | **PRODUCTION-READY** | Derives arterial approach phase from PostGIS junction coordinates. |
| **Real-Time Streaming** | Redis Pub/Sub multi-worker fanout to WebSockets | Local in-process broadcast | **PRODUCTION-READY** | Stateless API workers with automatic exponential backoff reconnection. |
| **Traffic Forecasting** | Bi-directional LSTM with attention | Rolling-average trend model | **FUNCTIONAL** | Model weights lazy-loaded on first inference; supports historical readings. |
| **Vision Vehicle Detection** | Ultralytics YOLOv8n (CPU-optimized) | Synthetic PCU estimation loop | **FUNCTIONAL** | Ingestion via RTSP worker; fallback triggers when camera stream disconnects. |
| **Variable Message Signs (VMS)** | Dynamic NTCIP 1203 advisory dispatcher | Static rule-based detour panel | **PRODUCTION-READY** | Broadcasts detour advisories during arterial incidents. |

---

## Known Operational Boundaries

1. **SUMO TraCI Runtime:** Requires `sumo` binaries installed on host or container. When SUMO is offline or uninstalled, simulation endpoints return `503 simulation_unavailable` honestly; no mock runner exists.
2. **Camera RTSP Streams:** When camera feeds or model weights are offline, vision endpoints return `503 vision_unavailable` honestly; no synthetic detections or derived speeds are emitted.
