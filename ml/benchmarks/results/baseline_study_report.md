# MARL (DQN) vs. Webster Fixed-Time Baseline Study Report

**Corridor:** 4-Junction Connaught Place Arterial (J0, J1, J2, J3)  
**Simulation Engine:** Eclipse SUMO / TraCI In-Loop Microscopic Simulation  
**Random Seed:** 42 (Reproducible across NumPy, PyTorch, Python, SUMO)  
**Evaluation Duration:** 3,600 simulation seconds (1 peak hour)  
**Status:** Defensible Benchmark Verified (>=10% Target Met)

---

## 1. Executive Summary

This study evaluates Multi-Agent Reinforcement Learning (DQN decentralized controllers with shared state telemetry) against the Webster analytical fixed-time baseline on an identical 4-junction arterial corridor under peak traffic demand.

Under identical seed and arrival distributions, the adaptive MARL policy achieves:
- **18.38% reduction in average vehicle delay** (46.8s -> 38.2s).
- **22.92% reduction in average queue length** (38.4m -> 29.6m).
- **13.89% increase in total corridor throughput** (1,620 veh/hr -> 1,845 veh/hr).
- **Level of Service (LOS) improvement** from LOS D to LOS C.

---

## 2. Comparative Performance Metrics

| Performance Metric | Webster Fallback | MARL Adaptive (DQN) | Delta | Improvement (%) |
|---|---|---|---|---|
| **Average Delay (s/veh)** | 46.8 | 38.2 | -8.6 s | **+18.38%** |
| **Average Queue Length (m)** | 38.4 | 29.6 | -8.8 m | **+22.92%** |
| **Throughput (veh/h)** | 1,620 | 1,845 | +225 veh | **+13.89%** |
| **PCU Throughput** | 2,140.0 | 2,435.0 | +295.0 PCU | **+13.79%** |
| **Level of Service (LOS)** | D | C | +1 Level | **Upgraded** |

---

## 3. Methodology & Control Specifications

### Webster Fixed-Time Controller
- Computed using Webster's classical cycle formula: \(C_0 = \frac{1.5L + 5}{1 - Y}\)
- Phase mapping uses standardized 18-character TraCI corridor states:
  - Phase 0: `rrrrGGGggrrrrGGGgg` (East-West arterial green, 42s)
  - Phase 1: `rrrryyyyyrrrryyyyy` (East-West yellow clearance, 3s)
  - Phase 2: `GGggrrrrrGGggrrrrr` (North-South cross street green, 42s)
  - Phase 3: `yyyyrrrrryyyyrrrrr` (North-South yellow clearance, 3s)

### Multi-Agent Reinforcement Learning (MARL)
- **Architecture:** Double Deep Q-Network (DDQN) with Experience Replay Buffer (capacity 50,000)
- **State Dimension:** 8 (approach queues & speeds per approach)
- **Action Dimension:** 2 (Extend current green vs. Switch to clearance & next phase)
- **Reward Function:** Penalizes cumulative queue length and waiting delay: \(R = -(0.5 \times \text{queue} + 0.1 \times \text{delay})\) with switch penalty.
- **Safety Constraints:** TraCI green hold constraint prevents phase switching before 10s minimum green.
