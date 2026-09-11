import os
import time
import uuid
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models.traffic import TrafficReading
from app.models.junction import Junction
from shared.exceptions import VisionUnavailable
from app.schemas.ml import (
    DetectionResult,
    PredictionResponse,
    TrainingStatus,
    TrainingStartRequest,
    ModelHealth,
    PredictionItem
)
from app.services.auth_service import require_role
from app.models.user import User
from shared.constants import DataSource


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

            class _UnavailableDetector:
                """Stands in for a detector that could not be constructed.

                It raises rather than returning zeros: an empty count is a
                claim that the camera saw no vehicles, which is not what
                happened.
                """
                model_loaded = False

                def detect_from_bytes(self, b):
                    raise VisionUnavailable(
                        "VehicleDetector could not be initialised on this worker"
                    )
            _detector = _UnavailableDetector()
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
# SN-001: this was previously seeded with invented metrics and advanced by an
# arithmetic loop without ever running a gradient step. Both are removed.
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
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
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
            density=analysis["density"],
            detections=analysis["detections"],
            processing_time_ms=elapsed_ms
        )
    except VisionUnavailable as e:
        # The detector has no weights, or inference failed. Either way there is
        # no detection to report; it previously returned five invented boxes.
        logger.warning(f"Detection unavailable: {e}")
        raise HTTPException(
            status_code=503,
            detail={"status": "vision_unavailable", "reason": str(e)},
        )
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        raise HTTPException(status_code=500, detail=f"Image processing error: {str(e)}")


@router.get("/predict/{junction_id}", response_model=PredictionResponse)
async def get_prediction(
    junction_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
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
                        # Null means the sensor did not report it. Substituting
                        # 30 km/h and a queue of 5 fed invented values straight
                        # into the model's input window.
                        "speed": float(r.avg_speed) if r.avg_speed is not None else None,
                        "queue": float(r.queue_length) if r.queue_length is not None else None,
                        "junction_id": junction_id
                    }
                    for r in reversed(db_readings)
                ]

        # 2. Check if forecaster has trained weights
        if (
            recent_readings
            and traffic_forecaster.is_lstm_trained
            and traffic_forecaster.is_xgb_trained
        ):
            try:
                # A prediction is only about this junction if it was computed
                # from this junction's observations. Feeding the model
                # generate_synthetic_data() when the table was empty produced a
                # curve about the data generator, returned under source="model"
                # as though it described the road.
                result = traffic_forecaster.predict(junction_id, recent_readings)

                return PredictionResponse(
                    junction_id=junction_id,
                    predictions=[PredictionItem(**p) for p in result['horizons']],
                    spillback_risk=round(result['spillback_risk'], 2),
                    source=DataSource.MODEL,
                    training_data="synthetic",
                    generated_at=datetime.utcnow()
                )
            except Exception as ml_err:
                logger.warning(f"Ensemble prediction error ({ml_err}), using dynamic flow model fallback.")

        # 3. Heuristic path (SN-006). Without observations there is nothing to
        #    extrapolate from, so the endpoint reports that rather than
        #    inventing a curve. The previous fallback derived its value from
        #    `sum(ord(c) for c in junction_id) % 15` — deterministic noise off
        #    the junction's name, which varies per junction and so reads as
        #    junction-specific insight while carrying no information about it.
        if not recent_readings:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "forecast_unavailable",
                    "reason": (
                        "no recent traffic readings for this junction and no "
                        "trained forecaster; a prediction would have no basis"
                    ),
                },
            )

        # Persistence baseline anchored on the last observed PCU, with a coarse
        # peak-hour factor. Crude, but every input is measured.
        last_pcu = float(recent_readings[-1]["pcu_value"])
        hour_ist = (datetime.utcnow().hour + 5) % 24
        peak = 1.15 if (8 <= hour_ist <= 11 or 17 <= hour_ist <= 21) else 1.0

        return PredictionResponse(
            junction_id=junction_id,
            predictions=[
                PredictionItem(minutes=15, predicted_pcu=round(last_pcu * peak, 1), confidence=None),
                PredictionItem(minutes=30, predicted_pcu=round(last_pcu * peak * 1.05, 1), confidence=None),
                PredictionItem(minutes=60, predicted_pcu=round(last_pcu * peak * 1.10, 1), confidence=None),
            ],
            spillback_risk=round(min(0.95, (last_pcu * peak) / 100.0), 2),
            source=DataSource.HEURISTIC,
            training_data=None,
            generated_at=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/start", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def start_training(
    req: TrainingStartRequest,
    current_user: User = Depends(require_role("ADMIN", action="ML_TRAIN"))
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
async def stop_training(current_user: User = Depends(require_role("ADMIN", action="ML_TRAIN"))):
    """Not implemented. See start_training."""
    raise HTTPException(
        status_code=501,
        detail="Training is not available through the API, so there is nothing to stop.",
    )


@router.get("/train/status", response_model=TrainingStatus)
async def get_training_status(current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))):
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
async def get_models_health(current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))):
    """Check health and availability of all AI models."""
    import shutil
    has_sumo = shutil.which("sumo") is not None or os.path.exists("/usr/bin/sumo")

    return ModelHealth(
        vision_model=vehicle_detector.model_loaded,
        forecaster_model=traffic_forecaster.is_lstm_trained and traffic_forecaster.is_xgb_trained,
        marl_agent=True,
        sumo_available=has_sumo,
        training_data="synthetic"
    )
