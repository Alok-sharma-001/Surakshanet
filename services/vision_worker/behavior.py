import math
import numpy as np
from typing import List, Dict, Optional, Tuple, Any
import logging

from services.vision_worker.config import CameraConfig
from services.vision_worker.tracker import Track

logger = logging.getLogger("surakshanet.vision.behavior")


class RashDrivingDetector:
    """Detects dangerous / rash driving via measurable kinematic proxies (SN-081).
    Does NOT assert legal guilt or intent — produces UNVERIFIED flags for operator review.
    
    Proxies:
    1. Excessive speed: > 1.3x limit sustained for 2s (requires calibration)
    2. Sudden lane changes: >= 3 transitions in 10s
    3. Weaving: lateral position variance sigma > 1.2m over 5s
    4. Unsafe headway: time gap to lead track < 0.8s
    5. Harsh braking: longitudinal deceleration > 4.0 m/s^2
    """

    def __init__(self, camera_config: CameraConfig):
        self.camera_config = camera_config
        # track_id -> dict of tracking states (sustained speed time, etc.)
        self._state: Dict[str, Dict[str, Any]] = {}
        self._flagged_tracks: set = set()

    def process_tracks(self, tracks: List[Track], timestamp: float) -> List[Dict[str, Any]]:
        new_flags = []
        mpp = self.camera_config.mpp
        limit_kmh = self.camera_config.speed_limit_kmh

        confirmed_tracks = [t for t in tracks if t.is_confirmed()]
        confirmed_ids = {t.track_id for t in confirmed_tracks}

        # Cleanup stale tracks
        for tid in list(self._state.keys()):
            if tid not in confirmed_ids:
                del self._state[tid]

        # Group by lane for headway evaluation
        lane_tracks: Dict[str, List[Track]] = {}
        for t in confirmed_tracks:
            if t.lane_id:
                lane_tracks.setdefault(t.lane_id, []).append(t)

        for track in confirmed_tracks:
            if track.track_id in self._flagged_tracks or track.rash_driving_flagged:
                continue

            st = self._state.setdefault(track.track_id, {
                "high_speed_start": None,
                "last_speed_mps": None,
                "last_speed_ts": None,
            })

            exceeded_proxies = {}

            # 1. Excessive speed (> 1.3x limit sustained 2 s)
            speed_kmh = track.get_speed_kmh(mpp, window_s=1.0)
            if speed_kmh is not None and limit_kmh > 0:
                speed_mps = speed_kmh / 3.6
                if speed_kmh > (1.3 * limit_kmh):
                    if st["high_speed_start"] is None:
                        st["high_speed_start"] = timestamp
                    elif (timestamp - st["high_speed_start"]) >= 2.0:
                        exceeded_proxies["excessive_speed"] = {
                            "speed_kmh": round(speed_kmh, 1),
                            "limit_kmh": limit_kmh,
                            "threshold_kmh": round(1.3 * limit_kmh, 1),
                            "sustained_s": round(timestamp - st["high_speed_start"], 2)
                        }
                else:
                    st["high_speed_start"] = None

                # 5. Harsh braking (> 4.0 m/s^2 deceleration evaluated over dt >= 0.3s)
                if st["last_speed_mps"] is not None and st["last_speed_ts"] is not None:
                    dt = timestamp - st["last_speed_ts"]
                    if dt >= 0.3:
                        decel = (st["last_speed_mps"] - speed_mps) / dt
                        if decel > 4.0 and st["last_speed_mps"] > 5.0:
                            exceeded_proxies["harsh_braking"] = {
                                "deceleration_mps2": round(decel, 2),
                                "threshold_mps2": 4.0
                            }
                        st["last_speed_mps"] = speed_mps
                        st["last_speed_ts"] = timestamp
                else:
                    st["last_speed_mps"] = speed_mps
                    st["last_speed_ts"] = timestamp

            # 2. Sudden lane change (>= 3 transitions in 10 s)
            recent_transitions = [
                trans for trans in track.lane_transitions
                if (timestamp - trans[1]) <= 10.0
            ]
            if len(recent_transitions) >= 3:
                exceeded_proxies["sudden_lane_change"] = {
                    "transitions_10s": len(recent_transitions),
                    "threshold": 3
                }

            # 3. Weaving (lateral position standard deviation > 1.2 m over 5 s)
            if len(track.history) >= 10:
                cutoff_5s = timestamp - 5.0
                pts_5s = [p for p in track.history if p[2] >= cutoff_5s]
                if len(pts_5s) >= 8:
                    xs = [p[0] for p in pts_5s]
                    ys = [p[1] for p in pts_5s]
                    # Compute lateral variance relative to principal axis of motion
                    # Project points onto perpendicular axis
                    dx = xs[-1] - xs[0]
                    dy = ys[-1] - ys[0]
                    norm = math.hypot(dx, dy)
                    if norm > 10.0:
                        # Perpendicular unit vector (-dy/norm, dx/norm)
                        perp_x, perp_y = -dy / norm, dx / norm
                        lateral_offsets = [(x - xs[0]) * perp_x + (y - ys[0]) * perp_y for x, y in zip(xs, ys)]
                        std_lat_px = float(np.std(lateral_offsets))
                        if mpp and mpp > 0:
                            std_lat_m = std_lat_px * mpp
                            if std_lat_m > 1.2:
                                exceeded_proxies["weaving"] = {
                                    "lateral_std_m": round(std_lat_m, 2),
                                    "threshold_m": 1.2
                                }

            # 4. Unsafe headway (< 0.8 s to lead track in same lane)
            if track.lane_id and track.lane_id in lane_tracks and mpp and speed_kmh and speed_kmh > 15.0:
                speed_mps = speed_kmh / 3.6
                cx, cy = track.centroid
                heading = track.get_heading(last_n=5)
                if heading is not None:
                    # Look for ahead tracks in same lane
                    lead_track = None
                    min_dist_m = float("inf")
                    for other in lane_tracks[track.lane_id]:
                        if other.track_id == track.track_id:
                            continue
                        ocx, ocy = other.centroid
                        # Vector from track to other
                        vox, voy = ocx - cx, ocy - cy
                        dist_m = math.hypot(vox, voy) * mpp
                        # Dot product with track motion direction
                        h_rad = math.radians(heading)
                        dir_x, dir_y = math.cos(h_rad), math.sin(h_rad)
                        proj = vox * dir_x + voy * dir_y
                        if proj > 0 and dist_m < min_dist_m:
                            min_dist_m = dist_m
                            lead_track = other

                    if lead_track and min_dist_m < float("inf"):
                        headway_s = min_dist_m / max(0.1, speed_mps)
                        if headway_s < 0.8:
                            exceeded_proxies["unsafe_headway"] = {
                                "headway_s": round(headway_s, 2),
                                "gap_distance_m": round(min_dist_m, 1),
                                "threshold_s": 0.8,
                                "lead_track_id": lead_track.track_id
                            }

            # If any proxy triggered, raise DANGEROUS_DRIVING flag
            if exceeded_proxies:
                self._flagged_tracks.add(track.track_id)
                track.rash_driving_flagged = True
                flag_payload = {
                    "flag_type": "DANGEROUS_DRIVING",
                    "camera_id": self.camera_config.id,
                    "track_id": track.track_id,
                    "confidence": round(track.confidence, 3),
                    "status": "UNVERIFIED",
                    "note": "Behaviour flagged for review. Not a confirmed violation.",
                    "evidence": {
                        "proxies_exceeded": list(exceeded_proxies.keys()),
                        "details": exceeded_proxies,
                        "vehicle_class": track.vehicle_class,
                        "bbox": list(track.bbox),
                        "centroid": [round(track.centroid[0], 1), round(track.centroid[1], 1)],
                    },
                    "source": "vision"
                }
                logger.warning(
                    f"[{self.camera_config.id}] DANGEROUS_DRIVING flagged on {track.track_id}: "
                    f"{list(exceeded_proxies.keys())}"
                )
                new_flags.append(flag_payload)

        return new_flags
