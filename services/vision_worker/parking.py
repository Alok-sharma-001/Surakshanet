import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
import logging

from services.vision_worker.config import point_in_polygon
from services.vision_worker.tracker import Track

logger = logging.getLogger("surakshanet.vision.parking")


class ParkingZone:
    """Represents a designated or operator-drawn restricted parking zone."""

    def __init__(
        self,
        zone_id: str,
        name: str,
        camera_id: str,
        polygon: List[List[float]],
        active_start_time: Optional[str] = None,  # "HH:MM"
        active_end_time: Optional[str] = None,    # "HH:MM"
        threshold_s: float = 180.0,
    ):
        self.zone_id = zone_id
        self.name = name
        self.camera_id = camera_id
        self.polygon = polygon
        self.active_start_time = active_start_time
        self.active_end_time = active_end_time
        self.threshold_s = threshold_s

    def is_active(self, current_dt: Optional[datetime] = None) -> bool:
        """Checks whether the restriction applies at current time of day."""
        if not self.active_start_time or not self.active_end_time:
            return True
        now = current_dt or datetime.utcnow()
        current_time_str = now.strftime("%H:%M")
        if self.active_start_time <= self.active_end_time:
            return self.active_start_time <= current_time_str <= self.active_end_time
        else:
            # Spans midnight
            return current_time_str >= self.active_start_time or current_time_str <= self.active_end_time

    def contains_point(self, x: float, y: float) -> bool:
        return point_in_polygon(x, y, self.polygon)


class NoParkingDetector:
    """No-parking detector with mandatory queue context suppression (SN-080).
    Suppresses false positives when vehicles are queued at red signals.
    """

    def __init__(
        self,
        camera_id: str,
        zones: Optional[List[ParkingZone]] = None,
        default_threshold_s: float = 180.0,
        displacement_threshold_px: float = 20.0,
        window_s: float = 30.0,
    ):
        self.camera_id = camera_id
        self.zones: List[ParkingZone] = zones or []
        self.default_threshold_s = default_threshold_s
        self.displacement_threshold_px = displacement_threshold_px
        self.window_s = window_s

        # (zone_id, track_id) -> dwell_seconds
        self._dwell_times: Dict[Tuple[str, str], float] = {}
        self._flagged_pairs: set = set()
        self._last_process_time: Optional[float] = None

    def add_zone(self, zone: ParkingZone):
        self.zones.append(zone)

    def set_zones(self, zones: List[ParkingZone]):
        self.zones = list(zones)

    def queue_context(
        self,
        tracks: List[Track],
        controlling_signal_red: bool = False,
        last_red_elapsed_s: Optional[float] = None,
    ) -> bool:
        """Checks if stationary vehicles are part of a traffic signal queue.
        Suppresses parking flags if:
        1. The controlling signal is red or was red in the last 60 seconds, OR
        2. Three or more tracks are stationary in a line / lane.
        """
        if controlling_signal_red:
            return True
        if last_red_elapsed_s is not None and last_red_elapsed_s < 60.0:
            return True

        # Check for platoon/queue of stationary tracks (>= 3 tracks)
        stationary_count = 0
        for track in tracks:
            if not track.is_confirmed():
                continue
            disp = track.get_displacement_over_seconds(self.window_s)
            if disp < self.displacement_threshold_px:
                stationary_count += 1
                if stationary_count >= 3:
                    return True

        return False

    def process_tracks(
        self,
        tracks: List[Track],
        timestamp: float,
        controlling_signal_red: bool = False,
        last_red_elapsed_s: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluates confirmed tracks against active restricted parking zones.
        Suppresses false alerts via queue_context.
        Returns list of new ILLEGAL_PARKING flag dicts.
        """
        new_flags = []
        dt = 0.1
        if self._last_process_time is not None:
            dt = max(0.01, min(2.0, timestamp - self._last_process_time))
        self._last_process_time = timestamp

        is_queue = self.queue_context(
            tracks,
            controlling_signal_red=controlling_signal_red,
            last_red_elapsed_s=last_red_elapsed_s
        )

        active_track_map = {t.track_id: t for t in tracks if t.is_confirmed()}

        # Prune stale tracking records
        for key in list(self._dwell_times.keys()):
            if key[1] not in active_track_map:
                del self._dwell_times[key]

        for zone in self.zones:
            if not zone.is_active():
                continue

            for track_id, track in active_track_map.items():
                cx, cy = track.centroid
                key = (zone.zone_id, track_id)

                if zone.contains_point(cx, cy):
                    disp = track.get_displacement_over_seconds(self.window_s)
                    if disp < self.displacement_threshold_px:
                        self._dwell_times[key] = self._dwell_times.get(key, 0.0) + dt
                    else:
                        self._dwell_times[key] = 0.0

                    dwell_s = self._dwell_times.get(key, 0.0)
                    thresh = zone.threshold_s or self.default_threshold_s

                    # Only flag if dwell time exceeded AND not suppressed by queue context
                    if dwell_s >= thresh and not is_queue and key not in self._flagged_pairs:
                        self._flagged_pairs.add(key)
                        track.illegal_parking_flagged = True

                        flag_payload = {
                            "flag_type": "ILLEGAL_PARKING",
                            "camera_id": self.camera_id,
                            "track_id": track.track_id,
                            "confidence": round(track.confidence, 3),
                            "status": "UNVERIFIED",
                            "note": "Behaviour flagged for review. Not a confirmed violation.",
                            "evidence": {
                                "zone_id": zone.zone_id,
                                "zone_name": zone.name,
                                "dwell_s": round(dwell_s, 1),
                                "threshold_s": thresh,
                                "displacement_px": round(disp, 1),
                                "vehicle_class": track.vehicle_class,
                                "queue_suppressed": False,
                                "bbox": list(track.bbox),
                                "centroid": [round(cx, 1), round(cy, 1)],
                            },
                            "source": "vision"
                        }
                        logger.warning(
                            f"[{self.camera_id}] ILLEGAL_PARKING detected on track {track.track_id} "
                            f"in zone '{zone.name}' (dwell={dwell_s:.1f}s >= {thresh:.1f}s)"
                        )
                        new_flags.append(flag_payload)
                else:
                    # Outside zone
                    self._dwell_times[key] = 0.0

        return new_flags
