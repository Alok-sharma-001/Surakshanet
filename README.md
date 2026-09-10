# Surakshanet — Intelligent Transportation System (ITS)

Surakshanet is an Intelligent Transportation System designed for urban traffic monitoring, spatial junction management, adaptive signal optimization, and operator observability.

> **Implementation Status & Roadmap:**
> This repository is undergoing a 10-phase architectural hardening per the independent code audit.
> Current progress and specifications are documented in [`docs/`](docs/00-project-overview.md) and tracked in [`docs/CHECKLIST.md`](docs/CHECKLIST.md).
> All telemetry and prediction payloads enforce explicit data provenance (`DataSource`: `sumo`, `vision`, `mqtt`, `model`, `heuristic`, `manual`).

---

## Capability Status

| Capability | Current State | Subsystem & Roadmap Phase |
| :--- | :--- | :--- |
| **Spatial Junction Master** | **Implemented** | PostgreSQL 15 + PostGIS (`ST_DWithin`, spatial queries, GiST indexing) |
| **Telemetry Ingestion & Storage** | **Implemented** | TimescaleDB hypertable (`traffic_readings`) + MQTT Mosquitto broker |
| **Auth & Security** | **Implemented** | JWT OAuth2 authentication, role checks, password hashing |
| **Micro-Simulation Environment** | **Simulated** | Eclipse SUMO corridor simulation via TraCI bridge (`simulation/`) |
| **A* Traffic Routing** | **Implemented** | Network graph pathfinding with congestion cost weights (`backend/app/api/routing.py`) |
| **Object Detection (Vision)** | **Implemented (Standalone)** | YOLOv8 vehicle detection on frame upload (`POST /ml/detect`) |
| **Signal Control (MARL)** | **Planned (Phase 2)** | Pre-trained DQN weights exist; live inference loop connects in Phase 2 (`services/control_service/`) |
| **Emergency Green Corridor** | **Planned (Phase 3)** | Rolling ETA preemption & signal plan restore (`docs/10-emergency-corridor.md`) |
| **Public Citizen Advisory** | **Planned (Phase 4)** | Public unauthenticated traffic bulletin API (`docs/12-citizen-advisory.md`) |

---

## System Architecture

Surakshanet utilizes an event-driven architecture connecting micro-simulation, telemetry ingestion, spatial database, and operator dashboard:

```
                  ┌─────────────────────────────────────────┐
                  │          Edge Telemetry Sources         │
                  │  (Inductive Loops, Cameras, SUMO Sim)   │
                  └────────────────────┬────────────────────┘
                                       │ MQTT (surakshanet/junctions/{id}/telemetry)
                                       ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           Edge Ingress & Messaging                        │
│   • Mosquitto MQTT Broker (1883)                                          │
│   • Redis Pub/Sub Message Fanout & Cache (6379)                           │
└──────────────────────────────────────┬────────────────────────────────────┘
                                       │
                                       ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Application                             │
│   • REST Endpoints (/api/v1/traffic, /junctions, /ml, /routing, /alerts)  │
│   • PostGIS Spatial Queries & TimescaleDB Telemetry Ingestion            │
│   • Signal State Machine & Controller Mode API (Webster / MARL / Manual)  │
│   • Real-Time WebSocket Connection Manager (Redis Pub/Sub Fanout)         │
│   • Mandatory Data Provenance on Every Payload (DataSource contract)      │
└──────────────┬─────────────────────────────────────────────┬──────────────┘
               │                                             │
               ▼                                             ▼
┌───────────────────────────────┐             ┌─────────────────────────────┐
│ Consolidated Spatial Database │             │      Frontend Dashboard     │
│   • TimescaleDB + PostGIS     │             │   • Vite + React 18 + TS    │
│   • Port 5432 (or 5434 host)  │             │   • Data-Provenance Badges  │
│   • Spatial GiST Indexes      │             │   • Real-Time Map & Telemetry│
│   • 7-Day Chunk Hypertables   │             │   • Zero Client-Side Fakes  │
└───────────────────────────────┘             └─────────────────────────────┘
```

---

## Port Allocations & Network Topology

The table below outlines all exposed ports across Docker containers and host mappings:

| Service | Internal Port | Host Port | Protocol | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Nginx Ingress** | 80 / 443 | 80 / 443 | HTTP / HTTPS | Reverse proxy, TLS termination, HSTS enforcement |
| **FastAPI Backend** | 8000 | 8000 | HTTP / WS | Core REST API, WebSockets, Prometheus metrics |
| **TimescaleDB / PostGIS** | 5432 | 5432 / 5434 | TCP / PostgreSQL | Consolidated spatial junction data & hypertable telemetry |
| **Redis** | 6379 | 6379 | TCP / RESP | Token revocation denylist, WebSocket pub/sub fanout |
| **Mosquitto MQTT** | 1883 | 1883 | TCP / MQTT | IoT telemetry ingestion and edge controller commands |
| **Prometheus** | 9090 | 9090 | HTTP | Metrics collection and performance instrumentation |
| **Grafana** | 3000 | 3000 | HTTP | Operator monitoring and corridor telemetry dashboards |

---

## Environment Configuration

Key environment variables specified in `.env` (derived from `.env.example`):

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Deployment mode (`production`, `development`, `testing`) |
| `JWT_SECRET_KEY` | *(secret)* | Secret key for HS256 JWT validation (production requires non-default) |
| `DATABASE_URL` | `postgresql+asyncpg://...:5432/surakshanet` | Consolidated TimescaleDB + PostGIS connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL for caching and pub/sub |
| `MQTT_BROKER_HOST` | `mosquitto` | Host address of Mosquitto broker |
| `MQTT_BROKER_PORT` | `1883` | Port for MQTT communications |
| `HOST` | `0.0.0.0` | Backend bind host |
| `PORT` | `8000` | Backend HTTP/WS port |
| `WORKERS` | `2` | Number of Uvicorn worker processes |

---

## Quickstart & Operations Runbook

### Starting the Production Stack

```bash
# 1. Copy configuration
cp .env.example .env

# 2. Build and launch all infrastructure containers
make up
# or
docker compose -f infra/docker-compose.yml up -d

# 3. Apply database migrations
make migrate
# or
docker exec surakshanet-backend alembic upgrade head

# 4. Verify system health
make smoke
# or
./scripts/smoke_check.sh http://localhost:8000
```

### Stopping Services

```bash
make down
# or
docker compose -f infra/docker-compose.yml down
```

---

## Database Migrations & Backup Procedures

### Applying Migrations

Alembic manages all schema changes on the consolidated PostGIS + TimescaleDB engine:

```bash
docker exec surakshanet-backend alembic upgrade head
```

### Database Backup Procedure (`pg_dump`)

To take a complete backup of the spatial junction topologies and hypertable telemetry:

```bash
# Create timestamped SQL dump
docker exec -t surakshanet-timescaledb pg_dump -U surakshanet -d surakshanet -Fc > backup_surakshanet_$(date +%Y%m%d_%H%M%S).dump

# Restore from backup dump
docker exec -i surakshanet-timescaledb pg_restore -U surakshanet -d surakshanet -c < backup_surakshanet_20260906.dump
```

---

## Emergency Vehicle Corridor Preemption (Roadmap Phase 3)

The emergency corridor architecture specifies rolling ETA-based preemption with signal plan restore and cross-street starvation protection (specified in [`docs/10-emergency-corridor.md`](docs/10-emergency-corridor.md)).

### Activating Route Preemption via REST API

Authorized emergency operators can dispatch signal overrides for approaching emergency vehicles:

```bash
curl -X POST http://localhost:8000/api/v1/emergency/activate \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": "AMBULANCE_108",
    "corridor": ["J1", "J2", "J3", "J4"],
    "priority": "CRITICAL",
    "vehicle_type": "AMBULANCE"
  }'
```

This triggers:
1. Dynamic topological analysis determining the arterial approach heading (Phase 0: `rrrrGGGggrrrrGGGgg`).
2. Immediate MQTT command publishing to signal cabinets (`surakshanet/junctions/{id}/control`).
3. Multi-worker real-time WebSocket broadcast via Redis pub/sub (`surakshanet:events:alerts`).

### Deactivating Preemption

```bash
curl -X POST http://localhost:8000/api/v1/emergency/deactivate/AMBULANCE_108 \
  -H "Authorization: Bearer <TOKEN>"
```

---

## Testing & Quality Verification

Run all test suites across backend, frontend, and end-to-end integration:

```bash
# Run full automated test suite
make test

# Run backend unit and integration tests (pytest)
make test-backend

# Run frontend test suite (vitest)
make test-frontend

# Run comprehensive E2E test harness (326 test cases)
make test-e2e
```

---

## Troubleshooting & Diagnostic FAQ

### Q1: `surakshanet-backend` fails to start in production mode
**Cause:** Default credentials or fallback JWT secret detected while `ENVIRONMENT=production`.  
**Resolution:** Set a unique 256-bit `JWT_SECRET_KEY` and non-default database password in `.env`.

### Q2: WebSocket clients intermittently disconnect or fail across workers
**Cause:** Stateless backend workers require Redis pub/sub for cross-process connection fanout.  
**Resolution:** Verify Redis is healthy: `docker exec surakshanet-redis redis-cli ping`. Check logs with `docker logs surakshanet-backend`.

### Q3: Frontend bundle warning: chunk size exceeds 500 kB
**Cause:** Monolithic imports of large visualization libraries (Three.js, MapLibre).  
**Resolution:** Use code-split vendor chunks configured in `frontend/dashboard/vite.config.ts`. Run `npm run build` to verify chunk budgets.

---

## License

This project is licensed under the [MIT License](LICENSE).
