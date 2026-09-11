import os
import cv2
import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger("surakshanet.vision.privacy")


def blur_bounding_box(image: np.ndarray, bbox: List[float], ksize: int = 51) -> np.ndarray:
    """Applies heavy Gaussian blur to a bounding box [x1, y1, x2, y2] in the image."""
    h, w = image.shape[:2]
    x1 = max(0, min(w - 1, int(bbox[0])))
    y1 = max(0, min(h - 1, int(bbox[1])))
    x2 = max(0, min(w, int(bbox[2])))
    y2 = max(0, min(h, int(bbox[3])))

    if x2 <= x1 or y2 <= y1:
        return image

    roi = image[y1:y2, x1:x2]
    # Ensure kernel size is odd and >= 3
    k = max(3, ksize if ksize % 2 == 1 else ksize + 1)
    blurred_roi = cv2.GaussianBlur(roi, (k, k), 30)
    image[y1:y2, x1:x2] = blurred_roi
    return image


class PrivacyBlurrer:
    """Enforces privacy-by-default (SN-107, SN-109).
    Blurs license plates and detected face regions before saving frames or snapshots.
    ANPR is disabled by default.
    """

    def __init__(self, anpr_enabled: bool = False):
        self.anpr_enabled = anpr_enabled
        self._face_cascade = None
        # Load OpenCV Haar cascade if available
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml" if hasattr(cv2, "data") else ""
        if os.path.exists(cascade_path):
            try:
                self._face_cascade = cv2.CascadeClassifier(cascade_path)
            except Exception as e:
                logger.debug(f"Could not load face cascade: {e}")

    def blur_sensitive_areas(
        self,
        frame: np.ndarray,
        vehicle_boxes: Optional[List[List[float]]] = None,
        face_boxes: Optional[List[List[float]]] = None
    ) -> np.ndarray:
        """Returns a frame with all sensitive regions (faces, license plate zones) blurred."""
        blurred = frame.copy()

        # 1. Blur explicitly provided face boxes
        if face_boxes:
            for fbox in face_boxes:
                blur_bounding_box(blurred, fbox, ksize=35)

        # 2. Automatically detect and blur faces if cascade loaded
        elif self._face_cascade is not None:
            try:
                gray = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
                faces = self._face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                for (x, y, w, h) in faces:
                    blur_bounding_box(blurred, [x, y, x + w, y + h], ksize=35)
            except Exception:
                pass

        # 3. If ANPR is disabled, blur lower central region of detected vehicles where plates sit
        if not self.anpr_enabled and vehicle_boxes:
            for vbox in vehicle_boxes:
                vx1, vy1, vx2, vy2 = vbox
                vh = vy2 - vy1
                vw = vx2 - vx1
                # Lower 30% of vehicle box where plate is located
                plate_y1 = vy1 + 0.70 * vh
                plate_y2 = vy2
                plate_x1 = vx1 + 0.20 * vw
                plate_x2 = vx2 - 0.20 * vw
                blur_bounding_box(blurred, [plate_x1, plate_y1, plate_x2, plate_y2], ksize=25)

        return blurred
