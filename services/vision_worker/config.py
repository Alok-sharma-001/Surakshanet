import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import logging

logger = logging.getLogger("surakshanet.vision.config")


def point_in_polygon(x: float, y: float, polygon: List[List[float]]) -> bool:
    """Ray-casting point-in-polygon algorithm.
    Returns True if (x, y) is inside the polygon vertices.
    """
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if min(p1y, p2y) < y <= max(p1y, p2y):
            if x <= max(p1x, p2x):
                if p1y != p2y:
                    xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                else:
                    xinters = p1x
                if p1x == p2x or x <= xinters:
                    inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def polygon_area(polygon: List[List[float]]) -> float:
    """Computes area of polygon in square pixels using Shoelace formula."""
    n = len(polygon)
    if n < 3:
        return 1.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    return abs(area) / 2.0


@dataclass
class LaneConfig:
    id: str
    direction: str  # "N", "E", "S", "W"
    polygon: List[List[float]]
    expected_heading_deg: float
    area: float = field(init=False)

    def __post_init__(self):
        self.area = max(1.0, polygon_area(self.polygon))

    def contains_point(self, x: float, y: float) -> bool:
        return point_in_polygon(x, y, self.polygon)


@dataclass
class CameraConfig:
    id: str
    junction_id: str
    source: str
    fps: float = 15.0
    mpp: Optional[float] = None  # metres per pixel (None when uncalibrated)
    homography: Optional[List[List[float]]] = None
    speed_limit_kmh: float = 50.0
    lanes: List[LaneConfig] = field(default_factory=list)

    def get_lane_for_point(self, x: float, y: float) -> Optional[LaneConfig]:
        for lane in self.lanes:
            if lane.contains_point(x, y):
                return lane
        return None


@dataclass
class VisionWorkerConfig:
    cameras: Dict[str, CameraConfig] = field(default_factory=dict)
    decode_fps: float = 15.0
    detect_interval: int = 3  # detect every 3rd frame (5 Hz at 15 fps)
    conf_threshold: float = 0.40
    aggregation_window_s: float = 2.0
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    anpr_enabled: bool = False  # SN-109: ANPR is disabled by default

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "VisionWorkerConfig":
        """Loads configuration from YAML file or defaults."""
        paths_to_try = []
        if config_path:
            paths_to_try.append(config_path)
        paths_to_try.extend([
            os.path.join(os.getcwd(), "config", "cameras.yaml"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "cameras.yaml"),
        ])

        chosen_path = None
        for p in paths_to_try:
            if p and os.path.exists(p):
                chosen_path = p
                break

        cameras: Dict[str, CameraConfig] = {}
        if chosen_path:
            try:
                with open(chosen_path, "r") as f:
                    data = yaml.safe_load(f) or {}
                raw_cameras = data.get("cameras", {})
                for cam_id, cdata in raw_cameras.items():
                    lanes = []
                    for ldata in cdata.get("lanes", []):
                        lanes.append(LaneConfig(
                            id=str(ldata.get("id", "L1")),
                            direction=str(ldata.get("direction", "N")),
                            polygon=ldata.get("polygon", []),
                            expected_heading_deg=float(ldata.get("expected_heading_deg", 0.0))
                        ))
                    cameras[cam_id] = CameraConfig(
                        id=cam_id,
                        junction_id=str(cdata.get("junction_id", "J0")),
                        source=str(cdata.get("source", "fixtures/demo.mp4")),
                        fps=float(cdata.get("fps", 15.0)),
                        mpp=float(cdata["mpp"]) if cdata.get("mpp") is not None else None,
                        speed_limit_kmh=float(cdata.get("speed_limit_kmh", 50.0)),
                        lanes=lanes
                    )
            except Exception as e:
                logger.warning(f"Error loading cameras.yaml from {chosen_path}: {e}. Using fallback.")

        # Fallback if no cameras defined in YAML
        if not cameras:
            cameras["CAM-01"] = CameraConfig(
                id="CAM-01",
                junction_id="J0",
                source="fixtures/demo.mp4",
                fps=15.0,
                mpp=0.05,
                speed_limit_kmh=50.0,
                lanes=[
                    LaneConfig(
                        id="L1",
                        direction="N",
                        polygon=[[120.0, 400.0], [300.0, 400.0], [320.0, 700.0], [100.0, 700.0]],
                        expected_heading_deg=94.0
                    ),
                    LaneConfig(
                        id="L2",
                        direction="S",
                        polygon=[[350.0, 400.0], [530.0, 400.0], [550.0, 700.0], [330.0, 700.0]],
                        expected_heading_deg=274.0
                    )
                ]
            )

        return cls(cameras=cameras)
