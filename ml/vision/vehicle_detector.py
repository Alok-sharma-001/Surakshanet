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
    from shared.constants import PCU_FACTORS, compute_pcu
except ImportError:
    PCU_FACTORS = {
        'car': 1.0,
        'motorcycle': 0.5,
        'bus': 3.0,
        'truck': 3.0,
        'auto_rickshaw': 1.0,
        'bicycle': 0.2,
        'lcv': 1.5,
    }
    def compute_pcu(vehicle_counts: Dict[str, float]) -> float:
        return round(sum(count * PCU_FACTORS.get(vclass, 1.0) for vclass, count in vehicle_counts.items()), 2)


def _ensure_nms_available():
    """Ensures Non-Maximum Suppression (NMS) is available, monkeypatching pure PyTorch NMS
    if custom torchvision C++ ops fail to load (e.g. CPU vs CUDA build mismatch).
    """
    try:
        import torchvision.ops
        import torch
        b = torch.tensor([[0.0, 0.0, 10.0, 10.0]])
        s = torch.tensor([0.9])
        torchvision.ops.nms(b, s, 0.5)
    except Exception:
        import torch
        import torchvision.ops
        import torchvision.ops.boxes

        def _py_nms(boxes, scores, iou_threshold):
            if boxes.numel() == 0:
                return torch.empty((0,), dtype=torch.long, device=boxes.device)
            x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
            areas = (x2 - x1) * (y2 - y1)
            order = scores.argsort(descending=True)
            keep = []
            while order.numel() > 0:
                i = order[0].item()
                keep.append(i)
                if order.numel() == 1:
                    break
                xx1 = torch.clamp(x1[order[1:]], min=x1[i])
                yy1 = torch.clamp(y1[order[1:]], min=y1[i])
                xx2 = torch.clamp(x2[order[1:]], max=x2[i])
                yy2 = torch.clamp(y2[order[1:]], max=y2[i])
                inter = torch.clamp(xx2 - xx1, min=0) * torch.clamp(yy2 - yy1, min=0)
                ovr = inter / (areas[i] + areas[order[1:]] - inter)
                order = order[torch.where(ovr <= iou_threshold)[0] + 1]
            return torch.tensor(keep, dtype=torch.long, device=boxes.device)

        torchvision.ops.nms = _py_nms
        torchvision.ops.boxes.nms = _py_nms


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
            _ensure_nms_available()
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
                        "class": class_name,
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
        """Computes total PCU from vehicle counts using the canonical engine."""
        return compute_pcu(vehicle_counts)

        
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
