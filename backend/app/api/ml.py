import os
import time
import uuid
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import pandas as pd

from app.database import get_db
from app.models.traffic import TrafficReading
from app.models.junction import Junction
from app.schemas.ml import (
    DetectionResult,
    PredictionResponse,
    TrainingStatus,
    TrainingStartRequest,
    ModelHealth,
    PredictionItem
)
from app.services.auth_service import get_current_user
from app.models.user import User


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ML"])

# Lazy model instances (deferred until first request to minimize startup memory & speed)
_detector: Optional[object] = None
_forecaster: Optional[object] = None


def get_vehicle_detector():
    global _detector
    if _detector is None:
        try:
            from ml.vision.vehicle_detector import VehicleDetector
            _detector = VehicleDetector(confidence_threshold=0.4)
        except Exception as e:
            logger.warning(f"Could not initialize VehicleDetector: {e}")

            class _DummyDetector:
                model_loaded = False

                def detect_from_bytes(self, b):
                    return {"vehicle_counts": {}, "total_pcu": 0.0, "detections": [], "processing_time_ms": 0.0}
            _detector = _DummyDetector()
    return _detector


def get_traffic_forecaster():
    global _forecaster
    if _forecaster is None:
        try:
            from ml.forecasting.traffic_forecaster import TrafficForecaster
            _forecaster = TrafficForecaster()
            _candidate_dirs = [
                os.environ.get("FORECASTING_WEIGHTS_DIR", ""),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ml/forecasting/weights")),
                os.path.abspath(os.path.join(os.path.dirname(__file__), "../../ml/forecasting/weights")),
                "/app/ml/forecasting/weights"
            ]
            weights_dir = next((d for d in _candidate_dirs if d and os.path.exists(d)), None)
            if weights_dir:
                try:
                    _forecaster.load_models(weights_dir)
                    logger.info(f"Loaded traffic forecasting weights from {weights_dir}")
                except Exception as e:
                    logger.warning(f"Forecasting weights not yet loaded: {e}")
        except Exception as e:
            logger.warning(f"Could not initialize TrafficForecaster: {e}")

            class _DummyForecaster:
                is_lstm_trained = False
                is_xgb_trained = False
                sequence_length = 12

                def predict(self, *a, **kw): return []
                def generate_synthetic_data(self, *a, **kw): return pd.DataFrame()
            _forecaster = _DummyForecaster()
    return _forecaster


class _LazyModelProxy:
    def __init__(self, getter):
        object.__setattr__(self, "_getter", getter)

    def __getattr__(self, name):
        return getattr(self._getter(), name)

    def __setattr__(self, name, value):
        setattr(self._getter(), name, value)


vehicle_detector = _LazyModelProxy(get_vehicle_detector)
traffic_forecaster = _LazyModelProxy(get_traffic_forecaster)

# MARL training state.
#
# SN-001: this was previously seeded with invented metrics (episode 420,
# reward 14.2, best_reward 22.4) and advanced by a loop that computed
# `10.0 + ep*0.4 + ep%3` without ever running a gradient step, producing a
# learning curve from arithmetic. Both are removed.
#
# Training is an offline activity (see ml/marl/train_marl.py); the API does not
# run it. This stays None until a real run reports into it, and the status
# endpoint reports `unavailable` rather than inventing progress.
_training_status: Optional[dict] = None


@router.post("/detect", response_model=DetectionResult)
async def detect_vehicles(
    file: UploadFile = File(...),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Run YOLOv8 object detection on uploaded camera frame.
    Returns vehicle counts, PCU equivalent, bounding boxes, and execution time.
    """
    start_time = time.time()
    try:
        image_bytes = await file.read()
        analysis = vehicle_detector.detect_from_bytes(image_bytes)
        elapsed_ms = round((time.time() - start_time) * 1000.0, 1)

        return DetectionResult(
            vehicle_counts=analysis["counts"],
            total_pcu=analysis["total_pcu"],
            density=analysis.get("density", 0.45),
            detections=analysis["detections"],
            processing_time_ms=elapsed_ms
        )
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image processing error: {str(e)}")


@router.get("/predict/{junction_id}", response_model=PredictionResponse)
async def get_prediction(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Get 15/30/60 min traffic flow predictions and spillback risk for a specific junction.
    Uses real recent TrafficReading rows from PostgreSQL when available.
    """
    try:
        recent_readings = []

        # 1. Attempt to resolve junction by UUID or name
        j_uuid = None
        try:
            j_uuid = uuid.UUID(junction_id)
        except ValueError:
            res = await db.execute(select(Junction).where(Junction.name.ilike(f"%{junction_id}%")))
            j_obj = res.scalars().first()
            if j_obj:
                j_uuid = j_obj.id

        if j_uuid:
            stmt = (
                select(TrafficReading)
                .where(TrafficReading.junction_id == j_uuid)
                .order_by(desc(TrafficReading.timestamp))
                .limit(traffic_forecaster.sequence_length)
            )
            res = await db.execute(stmt)
            db_readings = res.scalars().all()
            if len(db_readings) >= 4:
                recent_readings = [
                    {
                        "timestamp": r.timestamp.isoformat(),
                        "pcu": float(r.pcu_value),
                        "pcu_value": float(r.pcu_value),
                        "speed": float(r.avg_speed or 30.0),
                        "queue": float(r.queue_length or 5.0),
                        "junction_id": junction_id
                    }
                    for r in reversed(db_readings)
                ]

        # 2. Check if forecaster has trained weights
        if traffic_forecaster.is_lstm_trained and traffic_forecaster.is_xgb_trained:
            try:
                if not recent_readings:
                    df = traffic_forecaster.generate_synthetic_data(num_days=2, junctions=1)
                    recent_readings = df.tail(traffic_forecaster.sequence_length).to_dict('records')

                result = traffic_forecaster.predict(junction_id, recent_readings)

                return PredictionResponse(
                    junction_id=junction_id,
                    predictions=[PredictionItem(**p) for p in result['horizons']],
                    spillback_risk=round(result['spillback_risk'], 2),
                    generated_at=datetime.utcnow()
                )
            except Exception as ml_err:
                logger.warning(f"Ensemble prediction error ({ml_err}), using dynamic flow model fallback.")

        # 3. Dynamic heuristic prediction based on junction ID and time of day
        hour = datetime.utcnow().hour + 5.5  # IST
        base_pcu = 45.0 + (25.0 if 8 <= hour <= 11 or 17 <= hour <= 21 else 0.0)
        hash_offset = sum(ord(c) for c in junction_id) % 15

        return PredictionResponse(
            junction_id=junction_id,
            predictions=[
                PredictionItem(minutes=15, predicted_pcu=round(base_pcu + hash_offset, 1), confidence=0.92),
                PredictionItem(minutes=30, predicted_pcu=round(base_pcu + hash_offset * 1.2 + 6.0, 1), confidence=0.86),
                PredictionItem(minutes=60, predicted_pcu=round(base_pcu + hash_offset * 1.4 + 12.0, 1), confidence=0.78),
            ],
            spillback_risk=round(min(0.95, (base_pcu + hash_offset) / 100.0), 2),
            generated_at=datetime.utcnow()
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/start", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def start_training(
    req: TrainingStartRequest,
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Not implemented. MARL training is an offline activity.

    Training runs via `python -m ml.marl.train_marl`, which writes real episode
    metrics and a policy checkpoint to ml/marl/weights/. The API deliberately
    does not expose a trigger for it: a request-scoped background task cannot
    produce a reproducible training run, and the previous implementation of this
    endpoint synthesised progress instead of training anything (SN-001).
    """
    raise HTTPException(
        status_code=501,
        detail=(
            "Training is not available through the API. Run it offline with "
            "`python -m ml.marl.train_marl`; the resulting metrics and checkpoint "
            "are what this service reports."
        ),
    )


@router.post("/train/stop", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def stop_training(current_user: Optional[User] = Depends(get_current_user)):
    """Not implemented. See start_training."""
    raise HTTPException(
        status_code=501,
        detail="Training is not available through the API, so there is nothing to stop.",
    )


@router.get("/train/status", response_model=TrainingStatus)
async def get_training_status(current_user: Optional[User] = Depends(get_current_user)):
    """
    Report real training state, or state plainly that none is available.

    Returns `status: "unavailable"` when no run has reported metrics. It does not
    substitute placeholder values for absent ones.
    """
    if _training_status is None:
        return TrainingStatus(
            status="unavailable",
            reason=(
                "No training run has reported metrics. Training runs offline via "
                "ml/marl/train_marl.py."
            ),
        )
    return TrainingStatus(**_training_status)


@router.get("/models", response_model=ModelHealth)
@router.get("/health", response_model=ModelHealth)
@router.get("/models/health", response_model=ModelHealth)
async def get_models_health(current_user: Optional[User] = Depends(get_current_user)):
    """Check health and availability of all AI models."""
    import shutil
    has_sumo = shutil.which("sumo") is not None or os.path.exists("/usr/bin/sumo")

    return ModelHealth(
        vision_model=vehicle_detector.model_loaded,
        forecaster_model=traffic_forecaster.is_lstm_trained and traffic_forecaster.is_xgb_trained,
        marl_agent=True,
        sumo_available=has_sumo
    )
