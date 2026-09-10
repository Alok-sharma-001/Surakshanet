# Surakshanet Research Defense & System Architecture

## 1. System Philosophy & Architecture

Surakshanet is an Intelligent Transportation System (ITS) architected to bridge the gap between academic traffic simulation and physical edge deployment. Unlike conventional closed-loop traffic simulators, Surakshanet implements:
- **Heterogeneous Spatial Storage:** Unification of PostGIS spatial coordinate topology and TimescaleDB time-series hypertables under a single consolidated database engine.
- **Stateless Microservice Decoupling:** API workers maintain zero in-memory session state; WebSocket broadcasts and multi-junction coordination fan out across Redis Pub/Sub channels.
- **Deterministic Multi-Agent Signal Control:** Multi-Agent Reinforcement Learning (DQN) with discrete action masking and fixed random seeds to ensure verifiable, reproducible performance.

---

## 2. Empirical Benchmark: MARL vs. Webster Baseline

Empirical evaluation is conducted on a 4-junction urban arterial corridor (18 controlled directional link connections) modeled in SUMO (`simulation/networks/corridor.net.xml`) under realistic commuter traffic scenarios (e.g., morning surge).

### Experimental Configuration
- **Corridor Topology:** 4 signalized intersections (`J0`, `J1`, `J2`, `J3`) along a synchronized arterial corridor.
- **Evaluation Engine:** Automated A/B evaluation harness (`services/control_service/ab_runner.py`).
- **Webster Controller:** Dynamic cycle length computed using Webster's optimal formula \(C_0 = \frac{1.5L + 5}{1 - Y}\) with standardized 18-character phase strings (`rrrrGGGggrrrrGGGgg` / `GGggrrrrrGGggrrrrr`).
- **MARL (DQN) Controller:** Multi-agent Q-learning policy with real-time lane occupancy/queue state representation, action masking, and strict safety envelope enforcement.

### Benchmark Evaluation & Verification
All comparative benchmark runs are executed live against SUMO and persisted directly to the `ab_runs` PostgreSQL/TimescaleDB table via the `/ab/run` API endpoint. Metrics recorded for both baseline and MARL treatments include:
- Mean Vehicle Delay (s/veh)
- Mean Queue Length (veh)
- Total Completed Trips (veh)
- Calculated Improvement Metrics (%)

Pre-audit static claims (e.g. historical unverified percentages) have been deprecated in favor of dynamically verifiable, reproducible runs executed through `ABRunner`.

---

## 3. Telemetry Provenance & Integrity

To ensure that research results and live dashboard metrics are never conflated with synthetic or fallback data, every telemetry record and control decision enforces strict source tagging via the canonical `DataSource` enum (`shared/telemetry.py`):
- `sumo`: Physics-based SUMO TraCI simulation runs via induction loops and lane-area detectors.
- `vision`: Real-time edge camera detection inference (YOLOv8 / ByteTrack) from physical or RTSP streams.
- `mqtt`: Live sensor payloads ingested via the edge MQTT broker.
- `model`: State evaluations and actuation decisions produced by trained ML policies (e.g. MARL DQN).
- `heuristic`: Algorithmic baseline controllers (e.g. Webster fixed-time, actuated gap-out).
- `manual`: Direct operator interventions or safety overrides.

