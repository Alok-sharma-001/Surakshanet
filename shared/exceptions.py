"""Exceptions shared between the ML packages and the API layer.

These live outside `ml/` so the API can catch them without importing the
heavy model modules at startup, which would defeat the lazy loading in
`backend/app/api/ml.py`.
"""


class VisionUnavailable(RuntimeError):
    """Raised when the detector cannot produce a real detection.

    SN-004 removed five hardcoded bounding boxes at 88-96% confidence from the
    dashboard. The same five lived in `VehicleDetector._simulated_detections`,
    returned whenever ultralytics was missing or inference raised — so the API
    served invented boxes at invented confidences under the same shape as real
    YOLO output. There is no substitute for a detection: absence is reported.
    """
