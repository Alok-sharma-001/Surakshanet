# 13 — Computer Vision Pipeline

Covers **SN-069 … SN-082**. The audit found a genuine asset being displayed as a fake: real `yolov8n.pt` weights with real `ultralytics` inference exposed at `POST /ml/detect`, while the dashboard panel a judge actually looks at draws five hardcoded boxes drifting on `Math.random()` at 91–98% "confidence" (`ComputerVisionFeed.tsx:26–46`).

This phase converts the isolated endpoint into a pipeline and ships the highest-ROI behavioural detector.

---

## 1. Architecture

```
video source            frame          detection        tracking         classification
(file | loop | RTSP) ──▶ decode ──▶ YOLOv8n ──▶ IoU/centroid ──▶ class + PCU
                                                    tracker
                                                      │
        ┌─────────────────────────────────────────────┤
        ▼                                             ▼
  behaviour analysers                        approach aggregation
  (wrong-way, parking, rash)                          │
        │                                             ▼
        ▼                              canonical telemetry (source=vision)
  behavior_flags (UNVERIFIED)                         │
        │                                             ▼
        └──────────▶ Redis cv_detections      Redis traffic_updates
                             │                        │
                             ▼                        ▼
                         CV panel               CONTROL SERVICE
```

**Interchangeability requirement (Gate 5):** the control service consumes vision telemetry and SUMO telemetry through the identical schema. Only `source` differs. This is the architecture you would want in production, and it makes the demo claim honest.

---

## 2. Vision worker (SN-069 … SN-073)

**Location:** `services/vision_worker/`
```
main.py      lifecycle, source management, frame loop
tracker.py   IoU/centroid tracker, stable track IDs
wrongway.py  SN-076
parking.py   SN-080
behavior.py  SN-081
privacy.py   blur-by-default (SN-107)
config.py    cameras, lanes, zones, thresholds
```

Build on the existing `ml/vision/rtsp_stream_worker.py`, which is already the right shape.

| Parameter | Default | Notes |
|---|---|---|
| Source | `demo.mp4`, looped | `--source rtsp://…` for future live input |
| Decode rate | 15 fps | decouple from detection |
| Detection interval | every 3rd frame (≈5 Hz) | tracking fills the gaps |
| Confidence threshold | 0.40 | matches `VehicleDetector` default |
| Telemetry aggregation window | 2 s | matches SUMO bridge publish rate |
| Device | CPU | GPU optional; must not be required |

**Class mapping** stays as `VehicleDetector.CLASS_MAP` (COCO `1 bicycle, 2 car, 3 motorcycle, 5 bus, 7 truck`). COCO has no auto-rickshaw class — **say so**: auto-rickshaws are currently detected as `car` or `motorcycle`, which biases PCU. This is a stated limitation in [17-security-privacy.md §6](17-security-privacy.md), not something to paper over.

**Failure behaviour (SN-073), mandatory:**

| Condition | Response |
|---|---|
| No source configured | `GET /vision/status` → `{"status":"unavailable","reason":"no video source configured"}` |
| Decode error | same shape with the decode reason; no telemetry emitted |
| Model load failure | worker refuses to start, logs the path it tried |
| Frame backlog | drop frames, record `vision_frames_dropped_total`; never emit stale results as current |

**No synthetic detection is generated under any failure condition.**

---

## 3. Tracking (SN-071)

IoU-based association with centroid fallback; `max_age = 15` frames, `min_hits = 3` before a track is confirmed. Stable `track_id` per vehicle for the lifetime of its visibility.

Tracking is a prerequisite for everything in §5–§7 — wrong-way, dwell time and kinematics all need identity across frames. A per-frame detector cannot produce any of them, and claiming otherwise would be the same category of error the audit flagged.

---

## 4. PCU and telemetry (SN-072, SN-074)

**SN-074 — one PCU implementation.** `ml/vision/vehicle_detector.py` currently carries an inline duplicate `PCU_FACTORS` table that omits `lcv`. Delete it; import from `shared/constants.py`. A test asserts identical PCU for identical vehicle mixes across the vision, SUMO and MQTT paths.

Aggregation: per approach (from camera→approach mapping in `config.py`), over the 2 s window — vehicle count, PCU, mean speed (from track displacement × calibration), occupancy (bbox area over lane polygon area), queue length (stationary track count × average vehicle length). Emitted as `JunctionTelemetry` with `source=VISION`.

**Speed from a fixed camera requires calibration.** Each camera carries a homography or a metres-per-pixel factor in `config.py`. An uncalibrated camera emits `mean_speed_kmh: null` — not a guess.

---

## 5. Wrong-way detection (SN-075 … SN-077)

The audit's assessment: *the best CV win available* — near-zero false-positive rate, unambiguous output, high safety value, buildable in an afternoon on top of the existing detector. **If only one vision feature ships, ship this one.**

**Configuration (SN-075):** each camera declares lane polygons with an expected heading in degrees.
```yaml
cameras:
  CAM-01:
    lanes:
      - id: L1
        polygon: [[120,400],[300,400],[320,700],[100,700]]
        expected_heading_deg: 94
```

**Algorithm (SN-076):**
```
for each confirmed track inside a lane polygon:
    motion_heading = atan2(dy, dx) over the last N=10 positions
    delta = angular_difference(motion_heading, lane.expected_heading_deg)
    if delta > 135° and displacement > 15 px:
        opposed_frames += 1
    else:
        opposed_frames = 0
    if opposed_frames >= 30 (≈2 s at 15 fps) and not already flagged(track_id):
        raise WRONG_WAY flag
```

Sustained opposition over ~2 s, not a single frame. That threshold is what keeps the false-positive rate near zero through reversing manoeuvres, turns and tracking jitter.

**Output (SN-077):** a `behavior_flags` row, `status = UNVERIFIED`, with measured evidence (`motion_heading_deg`, `lane_heading_deg`, `opposed_frames`, `sustained_s`) and the mandatory note *"Behaviour flagged for review. Not a confirmed violation."* One flag per track — never a flag per frame.

---

## 6. No-parking detection (SN-079, SN-080)

**Zones (SN-079):** operator draws restricted polygons in the UI; stored via `POST /vision/zones` with an optional active time window (a no-parking zone may only apply 8 AM–8 PM).

**Algorithm (SN-080):**
```
for each confirmed track whose centroid is inside an active zone:
    if displacement over the last 30 s < 20 px:  dwell_s += Δt
    else:                                        dwell_s = 0
    if dwell_s > threshold (default 180 s) and not queue_context():
        raise ILLEGAL_PARKING flag
```

**`queue_context()` is essential.** A vehicle stopped at a red signal is not illegally parked. Suppress when: the controlling signal is red or was red in the last 60 s, **or** three or more tracks are stationary in a line within the same lane. Without this the detector fires on every red phase and is worthless.

Output: `behavior_flags` with type, duration, vehicle class, blurred snapshot, `UNVERIFIED`.

**ANPR is disabled by default (SN-109).** A config flag exists and is off; plates are blurred by `privacy.py`. The audit's judgement: restraint here reads as maturity, and one slide showing a blurred-plate pipeline earns more than a working ANPR demo.

---

## 7. Rash / dangerous driving (SN-081, SN-082)

Kinematic proxies only, from calibrated tracks:

| Proxy | Measure | Default threshold |
|---|---|---|
| Excessive speed | track speed vs. link limit | > 1.3 × limit sustained 2 s |
| Sudden lane change | lane-polygon transitions | ≥ 3 in 10 s |
| Weaving | lateral position variance | σ > 1.2 m over 5 s |
| Unsafe headway | gap to lead track / speed | < 0.8 s |
| Harsh braking | longitudinal deceleration | > 4 m/s² |

**Language policy (SN-082) — enforced by a repo-wide test:**

| Permitted | Forbidden |
|---|---|
| "Dangerous driving behaviour flagged for review" | "Violation detected" |
| "Behaviour flagged — unverified" | "Driver is guilty" / "Offence confirmed" |
| "3 of 5 indicators exceeded threshold" | any determination of intent or culpability |

Vision can measure kinematics. It cannot establish intent or legal culpability. The distinction lives in the **data model** — flags carry `UNVERIFIED` until an officer resolves them — not only in the slides.

---

## 8. CV panel (SN-078)

`frontend/dashboard/src/components/CommandCenter/ComputerVisionFeed.tsx` — replace entirely.

**Requirements:**
1. Every box corresponds to a `cv_detections` record received from the backend.
2. Confidence shown is the detector's actual confidence.
3. FPS shown is the worker's actual processing rate.
4. With the worker stopped, the panel shows **"No video source"** — not animated boxes.
5. Behaviour flags appear in a side list with `UNVERIFIED` badges and resolve/dismiss controls.
6. Displayed frames are blurred per [17-security-privacy.md](17-security-privacy.md).

**Acceptance:** `grep -n "Math.random" ComputerVisionFeed.tsx` returns nothing; stopping the worker changes the panel to the unavailable state within 5 s.

---

## 9. Acceptance criteria

1. Running the worker on the demo video writes `traffic_readings` rows with `source='vision'`.
2. The control service consumes vision telemetry without code changes (Gate 5).
3. Every box in the UI traces to a `cv_detections` row.
4. A wrong-way vehicle raises exactly one flag with measured evidence; a full normal-traffic run raises zero.
5. A vehicle queued at red raises no illegal-parking flag.
6. Every `behavior_flags` row starts `UNVERIFIED` and only an operator action changes it.
7. `pytest tests/test_language_policy.py` passes — no file claims a confirmed violation from vision alone.
8. PCU is identical across vision, SUMO and MQTT for the same vehicle mix.
9. ANPR flag defaults off; stored frames are blurred.
