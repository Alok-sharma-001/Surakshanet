# Original User Request

## Initial Request — 2026-09-06T13:32:00Z

Transform the Surakshanet Intelligent Transportation System (ITS) from an MVP into a secure, scalable, research-defensible, and production-ready system through systematic execution across security, data integrity, architecture, machine learning, frontend, and DevOps.

Working directory: /home/alok/surakshanet
Integrity mode: development

## Requirements

### R1. Security Hardening & Secret Remediation
- Restrict self-registration to operator roles only; require explicit administrative promotion.
- Move administrative credentials and authentication secrets to environment configuration with production safety checks.
- Remove tracked private keys (`surakshanet-key.pem`) and sensitive files from the index, enforce gitignore protection, rotate local environment credentials, and provide a standalone history rewrite script.
- Enforce CORS origin whitelisting compatible with credentialed requests, redirect insecure HTTP traffic to HTTPS, and harden token authentication lifecycle with revocation mechanisms.

### R2. Data Integrity, Spatial Storage & Schema Evolution
- Implement version-controlled database migrations (Alembic) replacing silent table creation.
- Consolidate database services to `timescaledb-ha`, activating native PostGIS geometry for spatial junction queries and TimescaleDB hypertables for traffic readings.
- Complete the traffic data access service against real database models and standardize MQTT telemetry topic schemas.
- Tag every telemetry and simulation event with its origin (`live`, `sim`, or `mock`) across all backend services.

### R3. Architecture, Scalability & Observability
- Decouple long-running simulation and ML workloads from API web workers into dedicated background worker services coordinated through Redis pub/sub.
- Implement cross-worker WebSocket broadcast fanout and lazy-load heavyweight ML models on demand.
- Standardize API error responses, request tracking middleware, and expand Prometheus instrumentation to cover WebSocket connections, message queues, and worker throughput.

### R4. ML & Simulation Rigor
- Conduct an empirical baseline study comparing Multi-Agent Reinforcement Learning (DQN) against Webster fixed-time signal control on an identical SUMO corridor scenario.
- Ensure training reproducibility with fixed random seeds, hyperparameter logging, and weight versioning.
- Derive signal green-wave phase mappings dynamically from network topology rather than static fallbacks.

### R5. Frontend Quality & User Experience
- Add automated unit and store testing using Vitest and React Testing Library, and configure lint verification in CI.
- Generate and enforce strict TypeScript definitions from the backend OpenAPI specification, eliminating `any` types in API clients.
- Implement route-level code splitting (`React.lazy` and `Suspense`), exponential backoff on WebSocket reconnection, and visual indicators for telemetry data sources.
- Commit current frontend enhancements (`design.md` and modified pages) and add proper error boundaries.

### R6. DevOps, Delivery & Documentation
- Upgrade CI workflow to run linting (`ruff`, `mypy`, `tsc`), execute database migrations, run full backend/frontend test suites, and enforce coverage thresholds.
- Implement automated deployment smoke checks validating `/health`, `/metrics`, and WebSocket connectivity.
- Add developer hygiene tooling (`Makefile`, pre-commit hooks, `.env.example` validation), a formal MIT `LICENSE` file, and an architectural operations runbook in `README.md`.

## Acceptance Criteria

### Security & Authentication
- [ ] Attempting registration with admin email patterns assigns `OPERATOR` role; admin privileges require explicit promotion.
- [ ] Application refuses to start in `ENVIRONMENT=production` if default secret or admin credentials are in use.
- [ ] `surakshanet-key.pem` and sensitive certificates are untracked in git, and `.gitignore` prevents re-addition.
- [ ] Insecure HTTP requests receive a 301 redirect to HTTPS with appropriate security headers.

### Database & Telemetry Integrity
- [ ] Database schema is initialized and updated exclusively via versioned Alembic migrations.
- [ ] Spatial queries utilize PostGIS geometry point columns with spatial indexes.
- [ ] Traffic telemetry records write to TimescaleDB hypertables with defined retention policies.
- [ ] Telemetry payloads across WebSocket and MQTT include verified `source: "sim" | "mock" | "live"` metadata.

### System Performance & ML Benchmarks
- [ ] WebSockets broadcast state across multiple independent web worker processes via Redis pub/sub without dropped connections.
- [ ] The MARL vs. Webster baseline study executes on SUMO corridor with reproducible seeds, recording >=10% improvement in queue length or average vehicle delay, with full results documented in an artifact.
- [ ] Heavyweight neural network models load on-demand rather than at module import.

### Client & Delivery Verification
- [ ] `npm test` runs automated frontend tests and passes cleanly.
- [ ] Frontend bundle exhibits route-level code splitting with no single JavaScript chunk exceeding recommended size warnings.
- [ ] All 41+ backend pytest test cases pass against the updated codebase.
- [ ] Complete CI pipeline passes linting, type-checking, migrations, and test execution.
- [ ] MIT `LICENSE` and comprehensive runbook documentation are added to the repository.
