import math
from typing import List, Dict, Optional, Tuple, Any
import logging

from services.vision_worker.config import CameraConfig, LaneConfig
from services.vision_worker.tracker import Track

logger = logging.getLogger("surakshanet.vision.wrongway")


def angular_difference(a: float, b: float) -> float:
    """Computes the shortest angular difference between two angles in degrees [0, 180]."""
    diff = abs((a - b + 180.0) % 360.0 - 180.0)
    return diff


class WrongWayDetector:
    """Detects wrong-way vehicle movements on declared lane geometries (SN-076).
    Requires sustained opposition (delta > 135 deg and displacement > 15px over >=30 frames)
    to eliminate false positives. Emits exactly one UNVERIFIED flag per violating track.
    """

    def __init__(self, camera_config: CameraConfig, min_opposed_frames: int = 30, fps: float = 15.0):
        self.camera_config = camera_config
        self.min_opposed_frames = min_opposed_frames
        self.fps = max(1.0, fps)
        # track_id -> int
        self._opposed_counts: Dict[str, int] = {}
        # track_id -> bool
        self._flagged_tracks: set = set()

    def process_tracks(self, tracks: List[Track], timestamp: float) -> List[Dict[str, Any]]:
        """Evaluates confirmed tracks against camera lane geometries.
        Returns list of new wrong-way behavior flag dicts ready for persistence.
        """
        new_flags = []
        active_track_ids = {t.track_id for t in tracks}

        # Clean up stale tracks from internal state
        for tid in list(self._opposed_counts.keys()):
            if tid not in active_track_ids:
                del self._opposed_counts[tid]

        for track in tracks:
            if not track.is_confirmed():
                continue

            # Check if centroid is within any declared lane polygon
            cx, cy = track.centroid
            lane = self.camera_config.get_lane_for_point(cx, cy)
            if not lane:
                self._opposed_counts[track.track_id] = 0
                continue

            track.record_lane(lane.id, timestamp)

            motion_heading = track.get_heading(last_n=10)
            displacement = track.get_displacement(last_n=10)

            if motion_heading is None:
                continue

            delta = angular_difference(motion_heading, lane.expected_heading_deg)

            # Check opposition condition per SN-076
            if delta > 135.0 and displacement > 15.0:
                count = self._opposed_counts.get(track.track_id, 0) + 1
                self._opposed_counts[track.track_id] = count
            else:
                self._opposed_counts[track.track_id] = 0

            # Trigger flag upon sustained opposition
            if self._opposed_counts.get(track.track_id, 0) >= self.min_opposed_frames:
                if track.track_id not in self._flagged_tracks and not track.wrong_way_flagged:
                    self._flagged_tracks.add(track.track_id)
                    track.wrong_way_flagged = True
                    sustained_s = round(self._opposed_counts[track.track_id] / self.fps, 2)

                    flag_payload = {
                        "flag_type": "WRONG_WAY",
                        "camera_id": self.camera_config.id,
                        "track_id": track.track_id,
                        "confidence": round(track.confidence, 3),
                        "status": "UNVERIFIED",
                        "note": "Behaviour flagged for review. Not a confirmed violation.",
                        "evidence": {
                            "lane_id": lane.id,
                            "lane_direction": lane.direction,
                            "motion_heading_deg": round(motion_heading, 1),
                            "lane_heading_deg": round(lane.expected_heading_deg, 1),
                            "heading_delta_deg": round(delta, 1),
                            "opposed_frames": self._opposed_counts[track.track_id],
                            "sustained_s": sustained_s,
                            "displacement_px": round(displacement, 1),
                            "vehicle_class": track.vehicle_class,
                            "bbox": list(track.bbox),
                            "centroid": [round(cx, 1), round(cy, 1)],
                        },
                        "source": "vision"
                    }
                    logger.warning(
                        f"[{self.camera_config.id}] WRONG-WAY detected on track {track.track_id} "
                        f"(lane {lane.id}, delta={delta:.1f}°, sustained={sustained_s}s)"
                    )
                    new_flags.append(flag_payload)

        return new_flags
