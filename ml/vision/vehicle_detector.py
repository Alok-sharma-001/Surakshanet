import logging
import numpy as np
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from shared.constants import PCU_FACTORS
except ImportError:
    PCU_FACTORS = {
        'car': 1.0,
        'motorcycle': 0.5,
        'bus': 3.0,
        'truck': 3.0,
        'auto_rickshaw': 1.0,
        'bicycle': 0.2
    }

class VehicleDetector:
    """YOLOv8 vehicle detection and PCU calculation service."""
    
    CLASS_MAP = {
        2: 'car',
        3: 'motorcycle',
        5: 'bus',
        7: 'truck',
        # Add auto_rickshaw, bicycle logic if needed, COCO doesn't explicitly have auto_rickshaw
        1: 'bicycle',
        8: 'auto_rickshaw' # Example custom class mapping
    }
    
    def __init__(self, model_path: str = 'yolov8n.pt', confidence_threshold: float = 0.5):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model_loaded = False
        self.model = None
        
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.model_loaded = True
            logger.info(f"Loaded YOLO model from {model_path}")
        except ImportError:
            logger.warning("ultralytics not installed. VehicleDetector running in dummy mode.")
        except Exception as e:
            logger.warning(f"Failed to load YOLO model: {e}")
            
    def detect_vehicles(self, frame: np.ndarray) -> List[Dict]:
        """Runs YOLOv8 inference on image frame."""
        if not self.model_loaded:
            return []
            
        results = self.model(frame, conf=self.confidence_threshold)[0]
        detections = []
        
        for box in results.boxes:
            cls_id = int(box.cls.item())
            if cls_id in self.CLASS_MAP:
                detections.append({
                    "bbox": box.xyxy[0].tolist(),
                    "class_name": self.CLASS_MAP[cls_id],
                    "confidence": box.conf.item()
                })
                
        return detections
        
    def count_by_class(self, detections: List[Dict]) -> Dict[str, int]:
        """Aggregates detection counts by vehicle class."""
        counts = {cls: 0 for cls in self.CLASS_MAP.values()}
        for det in detections:
            counts[det['class_name']] += 1
        return counts
        
    def calculate_pcu(self, vehicle_counts: Dict[str, int]) -> float:
        """Computes total PCU from vehicle counts."""
        pcu = 0.0
        for vclass, count in vehicle_counts.items():
            pcu += count * PCU_FACTORS.get(vclass, 1.0)
        return pcu
        
    def calculate_density(self, pcu: float, road_area_sqm: float) -> float:
        """Computes density in PCU/km (assuming road length).
        For this function, we assume road_area_sqm represents the area.
        Density = PCU / (Length in km). Let's assume standard width to derive length,
        or treat area as length. We'll simplify.
        """
        if road_area_sqm <= 0:
            return 0.0
        # Assume width is 7m (2 lanes), length = area/7
        length_km = (road_area_sqm / 7.0) / 1000.0
        if length_km <= 0:
            return 0.0
        return pcu / length_km
        
    def detect_and_analyze(self, frame: np.ndarray, zone_polygons: Optional[Dict] = None) -> Dict:
        """Full pipeline: detect -> count -> PCU -> density."""
        detections = self.detect_vehicles(frame)
        counts = self.count_by_class(detections)
        pcu = self.calculate_pcu(counts)
        
        result = {
            "detections": detections,
            "counts": counts,
            "total_pcu": pcu
        }
        
        # If zones provided, we would check point-in-polygon. Omitted for brevity, return overall.
        return result
