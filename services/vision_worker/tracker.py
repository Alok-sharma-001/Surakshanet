import math
import time
from typing import List, Dict, Optional, Tuple, Any
from collections import deque


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """Computes Intersection over Union (IoU) between two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = max(0.0, box1[2] - box1[0]) * max(0.0, box1[3] - box1[1])
    area2 = max(0.0, box2[2] - box2[0]) * max(0.0, box2[3] - box2[1])

    union = area1 + area2 - intersection
    if union <= 0.0:
        return 0.0
    return intersection / union


def compute_centroid(bbox: List[float]) -> Tuple[float, float]:
    """Computes centroid (cx, cy) of bounding box [x1, y1, x2, y2]."""
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


class Track:
    """Represents a tracked vehicle across video frames."""

    def __init__(self, track_id: str, bbox: List[float], vehicle_class: str, confidence: float, timestamp: float):
        self.track_id = track_id
        self.bbox = [float(v) for v in bbox]
        self.vehicle_class = vehicle_class
        self.confidence = float(confidence)
        self.hits = 1
        self.age = 1
        self.time_since_update = 0

        cx, cy = compute_centroid(self.bbox)
        # Store history of (cx, cy, timestamp, bbox)
        self.history: deque = deque(maxlen=300)
        self.history.append((cx, cy, timestamp, list(self.bbox)))

        self.last_seen_timestamp = timestamp
        self.lane_id: Optional[str] = None
        self.lane_transitions: List[Tuple[str, float]] = []  # (lane_id, timestamp)
        self.wrong_way_flagged = False
        self.illegal_parking_flagged = False
        self.rash_driving_flagged = False

    @property
    def centroid(self) -> Tuple[float, float]:
        return compute_centroid(self.bbox)

    def is_confirmed(self, min_hits: int = 3) -> bool:
        return self.hits >= min_hits

    def update(self, bbox: List[float], vehicle_class: str, confidence: float, timestamp: float):
        self.bbox = [float(v) for v in bbox]
        self.vehicle_class = vehicle_class
        self.confidence = float(confidence)
        self.hits += 1
        self.age += 1
        self.time_since_update = 0
        self.last_seen_timestamp = timestamp

        cx, cy = compute_centroid(self.bbox)
        self.history.append((cx, cy, timestamp, list(self.bbox)))

    def mark_missed(self):
        self.age += 1
        self.time_since_update += 1

    def record_lane(self, lane_id: Optional[str], timestamp: float):
        if lane_id and lane_id != self.lane_id:
            if self.lane_id is not None:
                self.lane_transitions.append((lane_id, timestamp))
            self.lane_id = lane_id

    def get_heading(self, last_n: int = 10) -> Optional[float]:
        """Calculates motion heading in degrees [0, 360) over the last N positions."""
        if len(self.history) < 2:
            return None
        pts = list(self.history)[-min(last_n, len(self.history)):]
        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]
        dist = math.hypot(dx, dy)
        if dist < 1e-4:
            return None
        rad = math.atan2(dy, dx)
        deg = math.degrees(rad) % 360.0
        return deg

    def get_displacement(self, last_n: int = 10) -> float:
        """Euclidean distance in pixels over the last N positions."""
        if len(self.history) < 2:
            return 0.0
        pts = list(self.history)[-min(last_n, len(self.history)):]
        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]
        return math.hypot(dx, dy)

    def get_displacement_over_seconds(self, window_s: float) -> float:
        """Euclidean distance in pixels over a time window."""
        if len(self.history) < 2:
            return 0.0
        now_ts = self.history[-1][2]
        cutoff = now_ts - window_s
        pts = [p for p in self.history if p[2] >= cutoff]
        if len(pts) < 2:
            pts = list(self.history)
        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]
        return math.hypot(dx, dy)

    def get_speed_kmh(self, mpp: Optional[float], window_s: float = 1.0) -> Optional[float]:
        """Computes calibrated speed in km/h over window_s. Returns None if uncalibrated."""
        if mpp is None or mpp <= 0.0:
            return None
        if len(self.history) < 2:
            return None
        now_ts = self.history[-1][2]
        cutoff = now_ts - window_s
        pts = [p for p in self.history if p[2] >= cutoff]
        if len(pts) < 2:
            return None
        dt = pts[-1][2] - pts[0][2]
        if dt <= 0.01:
            return None
        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]
        dist_px = math.hypot(dx, dy)
        dist_m = dist_px * mpp
        speed_mps = dist_m / dt
        return round(speed_mps * 3.6, 2)


class VehicleTracker:
    """IoU association tracker with centroid fallback (SN-071).
    Maintains stable track IDs across video frames.
    """

    def __init__(self, max_age: int = 15, min_hits: int = 3, iou_threshold: float = 0.3, centroid_dist_threshold: float = 60.0):
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        self.centroid_dist_threshold = centroid_dist_threshold
        self.tracks: Dict[str, Track] = {}
        self._next_id = 1

    def _allocate_track_id(self) -> str:
        tid = f"trk-{self._next_id}"
        self._next_id += 1
        return tid

    def update(
        self,
        detections: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[float] = None,
        is_detection_frame: bool = True
    ) -> List[Track]:
        """Updates tracker with list of detection dicts:
        [{'bbox': [x1, y1, x2, y2], 'class': str, 'confidence': float}, ...]
        Returns active confirmed tracks.
        When is_detection_frame is False, tracks are smoothly extrapolated forward without penalty (SN-071).
        """
        ts = timestamp if timestamp is not None else time.time()

        if not is_detection_frame:
            # Tracking fills the gaps between detector runs via kinematic extrapolation
            for tid, track in list(self.tracks.items()):
                if len(track.history) >= 2:
                    pts = list(track.history)
                    dt = ts - pts[-1][2]
                    prev_dt = pts[-1][2] - pts[-2][2]
                    if dt > 0 and prev_dt > 0:
                        vx = (pts[-1][0] - pts[-2][0]) / prev_dt
                        vy = (pts[-1][1] - pts[-2][1]) / prev_dt
                        dx = vx * dt
                        dy = vy * dt
                    else:
                        dx, dy = 0.0, 0.0
                else:
                    dx, dy = 0.0, 0.0

                # Cap displacement to reasonable limit (e.g. 50 px per step)
                disp = math.hypot(dx, dy)
                if disp > 50.0:
                    scale = 50.0 / disp
                    dx *= scale
                    dy *= scale

                new_bbox = [
                    track.bbox[0] + dx,
                    track.bbox[1] + dy,
                    track.bbox[2] + dx,
                    track.bbox[3] + dy,
                ]
                track.bbox = new_bbox
                cx, cy = compute_centroid(new_bbox)
                track.history.append((cx, cy, ts, list(new_bbox)))
                track.age += 1

            return [t for t in self.tracks.values() if t.is_confirmed(self.min_hits) and t.time_since_update <= 3]

        detections = detections or []
        track_ids = list(self.tracks.keys())
        unmatched_detections = set(range(len(detections)))
        unmatched_tracks = set(track_ids)

        # 1. First pass: IoU matching
        matches: List[Tuple[str, int, float]] = []
        for tid in track_ids:
            track = self.tracks[tid]
            best_iou = 0.0
            best_det_idx = -1
            for d_idx in unmatched_detections:
                iou = compute_iou(track.bbox, detections[d_idx]["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_det_idx = d_idx

            if best_iou >= self.iou_threshold and best_det_idx >= 0:
                matches.append((tid, best_det_idx, best_iou))

        # Sort matches by IoU descending
        matches.sort(key=lambda x: x[2], reverse=True)
        assigned_tracks = set()
        assigned_detections = set()
        for tid, d_idx, _ in matches:
            if tid not in assigned_tracks and d_idx not in assigned_detections:
                assigned_tracks.add(tid)
                assigned_detections.add(d_idx)
                det = detections[d_idx]
                det_cls = det.get("class") or det.get("class_name", "car")
                self.tracks[tid].update(det["bbox"], det_cls, det["confidence"], ts)
                unmatched_detections.discard(d_idx)
                unmatched_tracks.discard(tid)

        # 2. Second pass: Centroid distance fallback for remaining unmatched
        if unmatched_tracks and unmatched_detections:
            candidate_pairs = []
            for tid in unmatched_tracks:
                track = self.tracks[tid]
                tcx, tcy = track.centroid
                for d_idx in unmatched_detections:
                    det = detections[d_idx]
                    dcx, dcy = compute_centroid(det["bbox"])
                    dist = math.hypot(dcx - tcx, dcy - tcy)
                    if dist <= self.centroid_dist_threshold:
                        det_cls = det.get("class") or det.get("class_name", "car")
                        class_penalty = 0.0 if track.vehicle_class == det_cls else (self.centroid_dist_threshold * 0.25)
                        effective_dist = dist + class_penalty
                        if effective_dist <= self.centroid_dist_threshold:
                            candidate_pairs.append((effective_dist, tid, d_idx))

            candidate_pairs.sort(key=lambda x: x[0])
            for _, tid, d_idx in candidate_pairs:
                if tid in unmatched_tracks and d_idx in unmatched_detections:
                    det = detections[d_idx]
                    det_cls = det.get("class") or det.get("class_name", "car")
                    self.tracks[tid].update(det["bbox"], det_cls, det["confidence"], ts)
                    unmatched_tracks.discard(tid)
                    unmatched_detections.discard(d_idx)

        # 3. Create new tracks for remaining unmatched detections
        for d_idx in unmatched_detections:
            det = detections[d_idx]
            new_id = self._allocate_track_id()
            det_cls = det.get("class") or det.get("class_name", "car")
            self.tracks[new_id] = Track(
                track_id=new_id,
                bbox=det["bbox"],
                vehicle_class=det_cls,
                confidence=det["confidence"],
                timestamp=ts
            )

        # 4. Age unmatched tracks and cull dead tracks
        for tid in list(unmatched_tracks):
            self.tracks[tid].mark_missed()
            if self.tracks[tid].time_since_update > self.max_age:
                del self.tracks[tid]

        # Return list of confirmed active tracks (allow up to 1 missed frame buffer against jitter)
        return [t for t in self.tracks.values() if t.is_confirmed(self.min_hits) and t.time_since_update <= 1]

    def get_confirmed_tracks(self) -> List[Track]:
        return [t for t in self.tracks.values() if t.is_confirmed(self.min_hits)]
