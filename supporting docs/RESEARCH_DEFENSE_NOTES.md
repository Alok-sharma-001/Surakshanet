# Surakshanet: Intelligent Transportation & Traffic Optimization System
## Research Defense & Technical Companion Guide (INNOVIK 6.0)

This document provides the complete empirical, theoretical, and traffic engineering backing for the presentation deck `Intelligent_Transportation_System_New(1).pptx`.

---

### 1. Traffic Engineering & Statutory Standards (IRC Grounding)

#### A. Passenger Car Unit (PCU) Conversion (IRC:106-1990)
Standard computer vision pipelines fail in Indian traffic because raw vehicle counts do not capture physical road occupancy. Surakshanet calculates dynamic intersection load using the **Indian Roads Congress (IRC:106-1990)** standard:

37\text{Effective Junction Demand } (D_{\text{PCU}}) = \sum_{k \in K} N_k \times \text{PCU}_k37

Where:
* **2-Wheeler (Motorcycle / Scooter):** bash.5 \text{ PCU}$
* **Auto-Rickshaw (3-Wheeler):** .0 \text{ PCU}$
* **Passenger Car / Taxi:** .0 \text{ PCU}$
* **Light Commercial Vehicle (LCV):** .5 \text{ PCU}$
* **Standard City Bus / Heavy Truck:** .0 \text{ PCU}$

#### B. Signal Phase Constraints (IRC:93-1985 & Webster's Method)
* **Minimum Green Time:** {\min} = 10\text{ s}$ (ensures pedestrian clearance and prevents rapid signal hunting).
* **Amber / Clearance Interval:**  = 3.0\text{ s}$ to .0\text{ s}$.
* **All-Red Safety Interval:** {\text{all}} = 1.0\text{ s}$ to .0\text{ s}$ for intersection clearance.
* **Failsafe Local Fallback:** In the event of an edge sensor failure, the local signal controller defaults to a Time-of-Day (ToD) Webster cycle based on historical peak profiles.

---

### 2. State-of-the-Art (SOTA) Competitive Benchmarking

| Parameter | Fixed Timers (Current) | SCOOT / SCATS | C-DAC CoSiCoSt | Google Green Light | **Surakshanet (Proposed)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Adaptability** | None (Static) | Real-time adaptive | Vehicle-actuated | Monthly cloud recommendations | **Sub-second closed-loop dynamic** |
| **Indian Road Fit** | Poor | Poor (Assumes lanes) | Moderate | Moderate (GPS delay) | **High (IDD-calibrated PCU Vision)** |
| **Forecasting** | None | Reactive ($< 5\text{ min}$) | None (Reactive) | Historical aggregations | **15–60 min Predictive (LSTM+XGB)** |
| **Rerouting Sync** | Disconnected | Disconnected | Disconnected | Commuter-only (Reactive) | **Dual-Action (Signals + Commuters)** |
| **Capital Cost** | Low | High ($50k–$100k/junc) | High | Zero (Advisory only) | **Low (Edge Vision + Commodity IoT)** |

---

### 3. Algorithmic Formulation

#### A. Multi-Agent Reinforcement Learning (MARL) for Signal Control
* **State Space ($):** For intersection $ at time $:
  37s_t = \[ q_1^{\text{PCU}}, q_2^{\text{PCU}}, \dots, q_M^{\text{PCU}}, \, v_{\text{avg}}, \, t_{\text{elapsed}}, \, \Phi_{\text{current}} \]37
  where ^{\text{PCU}}$ is the queue length in PCUs on approach lane $, {\text{avg}}$ is approach velocity, {\text{elapsed}}$ is current phase duration, and $\Phi_{\text{current}}$ is current active green phase.

* **Action Space ($):** Discrete action  \in \{0, 1\}$:
  *  = 0$: Extend current green phase by $\Delta t = 5\text{ s}$ (up to {\max} = 60\text{ s}$).
  *  = 1$: Initiate transition to next phase (subject to {\text{elapsed}} \ge G_{\min}$).

* **Reward Function ($):**
  37R_t = - \left( \sum_{m=1}^M w_m q_m^{\text{PCU}} + \alpha \sum_{m=1}^M d_m \right) - \beta \cdot \mathbb{I}_{\text{switch}}37
  where $ is cumulative vehicle delay (seconds), $ is priority weight (e.g., {\text{emergency}} = 5.0$), and $\beta$ is a phase-switching penalty to prevent unnecessary cycling.

#### B. Spatio-Temporal Traffic Forecasting (LSTM + XGBoost)
* **Input Window:** Previous  = 60\text{ minutes}$ of 5-minute aggregated inflow, velocity, and upstream telemetry.
* **Prediction Horizon:** Multi-step ahead forecasting for +15\text{ min}$, +30\text{ min}$, and +60\text{ min}$.
* **Objective:** Predict queue spillback risk index $\mathcal{K}_{\text{spill}}$ to initiate green waves before physical saturation occurs.

---

### 4. Microscopic Simulation Setup (Eclipse SUMO + TraCI)

* **Simulation Environment:** Eclipse SUMO (Simulation of Urban MObility) v1.18+.
* **Control API:** Python `traci` (Traffic Control Interface) running at 0\text{ Hz}$ step frequency.
* **Corridor Model:** 4-junction multi-phase arterial network imported from OpenStreetMap (OSM).
* **Key Evaluation Metrics:**
  * **Average Delay per Vehicle:** Reduction from 4.2\text{ s}$ (Fixed) to 2.6\text{ s}$ (Surakshanet) $\rightarrow$ **hBc37.5\%*.
  * **Throughput:** Increased from ,820\text{ PCU/hr}$ to ,310\text{ PCU/hr}$ $\rightarrow$ **$+26.9\%*.
  * **Level of Service (LOS):** Improved from **LOS E** to **LOS C** during peak hours.
  * **Idle Emissions:** hBc21.4\%$ calculated via SUMO HBEFA (Handbook Emission Factors for Road Transport) v3.

---

### 5. Edge Hardware & Bandwidth Efficiency

* **Edge Compute Unit:** NVIDIA Jetson Orin Nano (8GB) / Raspberry Pi 5 with Hailo-8 AI acceleration.
* **Vision Model:** YOLOv8n / YOLOv8s converted to **TensorRT FP16 / INT8**.
* **Inference Speed:** 2\text{–}44\text{ FPS}$ on 080\text{p}$ RTSP camera streams.
* **Network Bandwidth:** Instead of transmitting raw 080\text{p}$ video streams (\text{–}8\text{ Mbps}$ per camera), the edge device publishes lightweight JSON telemetry via MQTT ($< 1.8\text{ KB/s}$ per junction), achieving **$>99\%$ reduction in cloud telemetry bandwidth**.
