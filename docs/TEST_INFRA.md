# SurakshaNet E2E Test Infrastructure & Architectural Guide

> [!IMPORTANT]
> **TEST REBUILD ROADMAP NOTICE**:
> For the authoritative test architecture, coverage philosophy, and critical path tests, refer to [`docs/19-testing.md`](docs/19-testing.md).

This document specifies the architecture, operational design, execution environment, and quality assurance framework for the SurakshaNet End-to-End (E2E) Test Suite.

The test suite provides a comprehensive, requirement-driven, opaque-box verification harness covering all 31 core features specified in `PROJECT.md` and `ORIGINAL_REQUEST.md`.

```
========================================================================================
                                 TEST SUITE AT A GLANCE
========================================================================================
 Tier 1 (Feature Coverage)       : 31 feature files × 5 tests  = 155 tests
 Tier 2 (Boundary & Corner Cases): 31 boundary files × 5 tests = 155 tests
 Tier 3 (Cross-Feature Combos)   : 1 suite × 12 pairwise tests =  12 tests
 Tier 4 (Real-World Scenarios)   : 1 suite × 4 full workflows  =   4 tests
----------------------------------------------------------------------------------------
 Total Test Suite Inventory      : 64 test modules             = 326 test cases
========================================================================================
```

---

## 2. Opaque-Box Architectural Philosophy

The SurakshaNet E2E test suite adheres strictly to **opaque-box principles**:

1. **Zero Internal Backend Imports**:
   - Test code **never** imports application internals (e.g., `from surakshanet.backend.* import ...`).
   - Tests have no knowledge of Python class hierarchies, internal ORM models, or private utility functions.

2. **Standard Protocol Boundaries**:
   All interactions with system components occur through public interfaces and transport boundaries:
   - **HTTP / REST API**: JSON payloads and response envelopes verified via `requests` over standard HTTP.
   - **WebSocket Streams**: Real-time traffic events and metric feeds verified via WebSocket framing.
   - **MQTT Telemetry**: Edge sensor ingestion simulated via `paho-mqtt` publishing to broker topics (`surakshanet/sensors/+/telemetry`).
   - **TimescaleDB / PostGIS**: External verification of persistent state using standard PostgreSQL wire protocol (`psycopg2` / DB-API) against published database schemas.
   - **Redis Key-Value & Pub/Sub**: External inspection of session cache, token blacklists, and broadcast channels.
   - **Prometheus Scrapes**: Validating metrics format and line protocol at `/metrics`.

3. **Requirement-Driven Assertions**:
   - Test inputs and expected behaviors are derived directly from the authoritative specifications in `PROJECT.md` and `ORIGINAL_REQUEST.md`.
   - The test suite functions as an independent oracle and verification gate for all milestone implementations (M1 through M6).

4. **Progressive Testability**:
   - Tests are tagged with milestone markers (`m1` through `m6`) and tier markers (`tier1` through `tier4`).
   - Tests for foundational milestones (e.g., M1 authentication, database setup, metrics) execute independently without requiring later milestones (e.g., M4 MARL or M5 Frontend) to be operational.

---

## 3. Service Topology & Test Environment

The E2E test environment orchestrates testing across the multi-container Docker topology configured in `docker-compose.yml`:

```
                                +---------------------------+
                                |    E2E Test Runner        |
                                | (python run_e2e_tests.py) |
                                +-------------+-------------+
                                              |
                   +--------------------------+--------------------------+
                   |                          |                          |
                   v                          v                          v
      [HTTP / REST & WebSocket]         [MQTT Protocol]         [PostgreSQL Wire]
                   |                          |                          |
                   v                          v                          v
        +--------------------+      +--------------------+     +--------------------+
        | surakshanet-backend|      |surakshanet-        |     |surakshanet-        |
        | FastAPI (Port 8000)|      |mosquitto (Port 1883)     |timescaledb (P 5432)|
        +----------+---------+      +--------------------+     +--------------------+
                   |                          ^
                   v                          |
        +--------------------+                |
        | surakshanet-redis  |----------------+
        |  Redis (Port 6379) |
        +--------------------+
```

### Environment Configuration & Service Endpoints

The test suite automatically resolves endpoints depending on whether the runner executes on the host machine or inside the Docker container network (`infra_surakshanet-network`):

| Service | Environment Variable | Container Default | Host Default | Protocol / Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Backend API** | `SURAKSHANET_BASE_URL` | `http://surakshanet-backend:8000` | `http://localhost:8000` | HTTP REST API / WebSocket |
| **TimescaleDB** | `DATABASE_URL` | `postgresql://postgres:postgres@surakshanet-timescaledb:5432/surakshanet` | `postgresql://postgres:postgres@localhost:5432/surakshanet` | Relational & Spatio-temporal DB |
| **Redis** | `REDIS_URL` | `redis://surakshanet-redis:6379/0` | `redis://localhost:6379/0` | Token revocation, fast state cache |
| **MQTT Broker** | `MQTT_BROKER_HOST` / `PORT`| `surakshanet-mosquitto` / `1883` | `localhost` / `1883` | Sensor and vehicle telemetry stream |
| **Prometheus** | `PROMETHEUS_URL` | `http://surakshanet-prometheus:9090` | `http://localhost:9090` | System and traffic metric scraping |
| **Nginx Proxy** | `NGINX_URL` | `http://surakshanet-nginx:80` | `http://localhost:80` | Reverse proxy and API gateway |

---

## 4. 4-Tier Test Suite Architecture

### Tier 1: Feature-by-Feature Coverage (155 Tests)
Directory: `tests/e2e/tier1_features/`
- Contains exactly 31 test modules (`test_f01_*.py` through `test_f31_*.py`).
- Every feature has a minimum of 5 focused test cases covering primary functional behavior (happy path, input validation, and expected responses).
- Highlights:
  - `F01`–`F05`: Operator authentication, password hashing, JWT expiration, token revocation, RBAC permissions.
  - `F06`–`F10`: TimescaleDB hypertables, PostGIS geospatial queries, Alembic migrations, traffic service integration.
  - `F11`–`F15`: Edge telemetry MQTT ingestion, worker queue decoupling, WebSocket fan-out, ML inference scaffolding, standardized error envelope (`error.code`, `error.message`, `request_id`).
  - `F16`–`F22`: Prometheus metrics scraping, SUMO 18-link corridor simulation, Webster baseline, MARL Q-learning agent, seed reproducibility, green wave corridor, baseline benchmark comparative analysis.
  - `F23`–`F27`: React/TypeScript frontend architecture, OpenAPI client generation, chunk budget (<500 kB), WebSocket reconnect badge, light/dark theme contrast and ErrorBoundary.
  - `F28`–`F31`: GitHub Actions CI pipeline, smoke check script, developer tooling/Makefile, deployment runbooks.

### Tier 2: Boundary & Corner Cases (155 Tests)
Directory: `tests/e2e/tier2_boundaries/`
- Contains exactly 31 boundary modules (`test_b01_*.py` through `test_b31_*.py`).
- Every feature has a minimum of 5 edge-case and boundary tests exercising failure modes, boundary limits, and adversarial inputs:
  - Payload boundaries (max email lengths, empty strings, Unicode characters, SQL injection patterns in search parameters).
  - Protocol limits (extreme JWT expiration ranges, expired tokens, revoked tokens, header injection in `X-Request-ID`).
  - Spatial & temporal limits (latitude/longitude outside [-90, 90] / [-180, 180], future timestamp boundaries, high-frequency MQTT bursts, QoS 0/1/2 handling).
  - Mathematical & algorithm boundaries (Webster division-by-zero protection on oversaturated flows, MARL observation clipping, seed overflow protection).
  - Web & asset boundaries (bundle chunk limits, exponential backoff caps, WCAG AAA/AA contrast compliance, JSDOM test runner isolation).

### Tier 3: Cross-Feature Integration Combinations (12 Tests)
Directory: `tests/e2e/tier3_combinations/`
Module: `test_cross_feature_combinations.py`
- Tests interaction between decoupled subsystems under realistic integration constraints:
  1. `F01` + `F05`: Authentication lifecycle combined with token revocation and blacklisting.
  2. `F01` + `F08`: RBAC role elevation coupled with PostGIS spatial query authorization.
  3. `F11` + `F09`: High-throughput MQTT sensor telemetry flowing into TimescaleDB hypertable chunks.
  4. `F10` + `F15`: Traffic service fault injection returning the RFC-7807/RFC-compliant standardized error envelope.
  5. `F13` + `F16`: High-frequency WebSocket client fan-out reflected in Prometheus telemetry gauges.
  6. `F12` + `F13`: Asynchronous Celery/Redis worker queue processing feeding real-time WebSocket streams.
  7. `F17` + `F18`: TraCI-driven SUMO 18-link corridor under Webster cycle-time control.
  8. `F21` + `F11`: Green wave corridor activation cross-verified with MQTT priority event logs.
  9. `F14` + `F16`: Lazy-loaded ML model serving verified against P99 inference latency metrics.
  10. `F24` + `F25`: Auto-generated OpenAPI TypeScript models validated against frontend route bundle sizes.
  11. `F26` + `F11`: WebSocket stream disconnect badge asserting source tagging during network reconnect.
  12. `F07` + `F06`: Alembic database migration rollback and re-apply preserving TimescaleDB hypertable policies.

### Tier 4: Real-World Application Scenarios (4 Tests)
Directory: `tests/e2e/tier4_scenarios/`
Module: `test_traffic_management_scenarios.py`
- Tests complete end-to-end multi-step traffic control workflows:
  1. **Corridor Peak Hour Congestion Workflow**:
     Operator signs in -> Queries corridor density -> Ingests surge telemetry -> Observes traffic metrics escalation -> Triggers signal plan change -> Validates congestion relief.
  2. **Emergency Vehicle Green Wave Preemption Workflow**:
     Ambulance dispatch registered -> Corridor junctions placed into priority override -> Normal signal cycle preempted -> Green wave established -> Vehicle exits corridor -> Normal Webster/MARL cycles safely restored.
  3. **Major Incident & Dynamic Rerouting Workflow**:
     Accident alert posted -> Junction status set to blocked -> Rerouting advisory broadcast over WebSocket -> PostGIS nearest-neighbor rerouting computed -> Incident cleared.
  4. **Telemetry Stream Failover & Data Reconciliation Workflow**:
     MQTT sensor stream disrupted -> System falls back to historical averages -> Connectivity restored -> Backlog telemetry ingested -> Data reconciled in TimescaleDB with zero duplicate records.

---

## 5. Unified Test Runner & CLI Usage

SurakshaNet provides both a dedicated executable runner script (`tests/e2e/run_e2e_tests.py`) and standard `pytest` integration.

### Dedicated Runner (`run_e2e_tests.py`)

```bash
# Run all 326 tests
python tests/e2e/run_e2e_tests.py

# Run specific tier
python tests/e2e/run_e2e_tests.py --tier 1
python tests/e2e/run_e2e_tests.py --tier 3

# Run specific milestone
python tests/e2e/run_e2e_tests.py --milestone m1
python tests/e2e/run_e2e_tests.py --milestone m2

# Run tests for a specific feature
python tests/e2e/run_e2e_tests.py --feature f01
python tests/e2e/run_e2e_tests.py --feature f16

# Dry run / discovery
python tests/e2e/run_e2e_tests.py --collect-only

# Verbose output with custom pytest filter
python tests/e2e/run_e2e_tests.py -v -k "emergency"
```

### Direct `pytest` Invocation

```bash
# Standard pytest execution
pytest tests/e2e

# Filter by tier marker
pytest tests/e2e -m tier1
pytest tests/e2e -m "tier3 or tier4"

# Filter by milestone marker
pytest tests/e2e -m m1
pytest tests/e2e -m "m1 and tier1"

# Generate JUnit XML or HTML report
pytest tests/e2e --junitxml=reports/e2e-results.xml
```

---

## 6. Test Data Isolation & Idempotency Rules

To prevent cross-test contamination and guarantee reliable reproducibility across test runs:

1. **Unique Identity Generation**:
   - Entities (users, junctions, sensor IDs) utilize UUID4 or microsecond timestamp suffixes (e.g., `operator_test_<uuid>@surakshanet.org`).
2. **Session Fixture Scoping**:
   - Shared client connections (HTTP, Redis, MQTT, DB) are pooled in `conftest.py` at the session scope to prevent socket exhaustion.
3. **Deterministic Seeds**:
   - For all stochastic tests (simulation generation, synthetic telemetry, MARL exploration), random seeds are fixed (`seed=42`) to guarantee reproducible outcomes.
4. **Non-Destructive Assertions**:
   - Tests do not drop production tables or flush live Redis instances; queries are scoped to test IDs or executed in rollbacked transactions.
