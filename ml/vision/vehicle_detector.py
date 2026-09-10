import os
import logging
import numpy as np
from typing import Dict, List, Optional
import io

from shared.exceptions import VisionUnavailable

logger = logging.getLogger(__name__)

# Re-exported so callers importing the detector can catch it from here too.
__all__ = ["VehicleDetector", "VisionUnavailable"]

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
    
    # Standard COCO dataset class mapping for traffic
    CLASS_MAP = {
        1: 'bicycle',
        2: 'car',
        3: 'motorcycle',
        5: 'bus',
        7: 'truck'
    }
    
    def __init__(self, model_path: Optional[str] = None, confidence_threshold: float = 0.4):
        # Locate local weights file if available
        default_local = os.path.join(os.path.dirname(__file__), "yolov8n.pt")
        if model_path is None or not os.path.exists(model_path):
            if os.path.exists(default_local):
                model_path = default_local
            else:
                model_path = model_path or "yolov8n.pt"

        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model_loaded = False
        self.model = None
        
        try:
            if os.path.exists(self.model_path):
                from ultralytics import YOLO
                self.model = YOLO(self.model_path)
                self.model_loaded = True
                logger.info(f"Loaded YOLO model from {self.model_path}")
            else:
                logger.warning(f"YOLO weights file {self.model_path} not found locally. Running in fallback mode.")
        except ImportError:
            logger.warning(
                "ultralytics not installed. Vehicle detection is UNAVAILABLE on this "
                "worker; it does not fall back to synthesised detections."
            )
        except Exception as e:
            logger.warning(
                f"Failed to load YOLO model ({e}). Vehicle detection is UNAVAILABLE; "
                "there is no fallback detection mode."
            )
            
    def detect_vehicles(self, frame: np.ndarray) -> List[Dict]:
        """Runs YOLOv8 inference on an OpenCV / NumPy image frame."""
        if not self.model_loaded or self.model is None:
            raise VisionUnavailable(
                "YOLO weights are not loaded; vehicle detection is unavailable. "
                "Install ultralytics and provide weights, or treat this junction "
                "as having no camera."
            )
            
        try:
            results = self.model(frame, conf=self.confidence_threshold)[0]
            detections = []
            
            for box in results.boxes:
                cls_id = int(box.cls.item())
                if cls_id in self.CLASS_MAP:
                    class_name = self.CLASS_MAP[cls_id]
                    bbox = box.xyxy[0].tolist()
                    
                    # Heuristic for Indian traffic: Compact square vehicles detected as cars
                    # are often auto-rickshaws (aspect ratio ~0.8-1.2, small bbox area)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                    area = w * h
                    if class_name == 'car' and 0.8 <= (h / max(1.0, w)) <= 1.25 and area < (frame.shape[0] * frame.shape[1] * 0.04):
                        class_name = 'auto_rickshaw'
                        
                    detections.append({
                        "bbox": bbox,
                        "class_name": class_name,
                        "confidence": float(box.conf.item())
                    })
                    
            return detections
        except Exception as e:
            logger.error(f"Inference error: {e}")
            raise VisionUnavailable(f"YOLO inference failed: {e}") from e
            
    def detect_from_bytes(self, image_bytes: bytes) -> Dict:
        """Decode image bytes and run complete vehicle analysis."""
        frame = None
        try:
            import cv2
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception:
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                frame = np.array(img)
            except Exception as e:
                logger.warning(f"Failed to decode image bytes: {e}")
                
        return self.detect_and_analyze(frame)

    def count_by_class(self, detections: List[Dict]) -> Dict[str, int]:
        """Aggregates detection counts by vehicle class."""
        classes = list(self.CLASS_MAP.values()) + ['auto_rickshaw']
        counts = {cls: 0 for cls in set(classes)}
        for det in detections:
            c = det.get('class_name', 'car')
            counts[c] = counts.get(c, 0) + 1
        return counts
        
    def calculate_pcu(self, vehicle_counts: Dict[str, int]) -> float:
        """Computes total PCU from vehicle counts."""
        pcu = 0.0
        for vclass, count in vehicle_counts.items():
            pcu += count * PCU_FACTORS.get(vclass, 1.0)
        return round(pcu, 2)
        
    def calculate_density(self, pcu: float, road_area_sqm: float = 7000.0) -> float:
        """Computes traffic density (0.0 to 1.0 scale)."""
        if road_area_sqm <= 0:
            return 0.0
        capacity_pcu = (road_area_sqm / 1000.0) * 150.0  # Approx 150 PCU / lane-km
        return round(float(np.clip(pcu / max(1.0, capacity_pcu), 0.0, 1.0)), 3)
        
    def detect_and_analyze(self, frame: Optional[np.ndarray]) -> Dict:
        """Full pipeline: detect -> count -> PCU -> density."""
        detections = self.detect_vehicles(frame)
        counts = self.count_by_class(detections)
        pcu = self.calculate_pcu(counts)
        density = self.calculate_density(pcu)
        
        return {
            "detections": detections,
            "counts": counts,
            "total_pcu": pcu,
            "density": density
        }
