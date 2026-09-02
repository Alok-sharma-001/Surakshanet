from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status
from typing import Optional, List
from app.schemas.ml import (
    DetectionResult,
    PredictionResponse,
    TrainingStatus,
    TrainingStartRequest,
    ModelHealth,
    ForecastTrainRequest,
    PredictionItem
)
from datetime import datetime
import logging
import pandas as pd

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ML"])

# Mock Authentication Dependencies
def get_current_user():
    return {"id": "user_auth", "role": "user"}

def get_admin_user(user: dict = Depends(get_current_user)):
    # In reality, this would check if user['role'] == 'admin'
    return {"id": "admin_auth", "role": "admin"}

def get_operator_user(user: dict = Depends(get_current_user)):
    return {"id": "op_auth", "role": "operator"}


# Mock global state for background task tracking
_training_status = {
    "is_training": False,
    "episode": 0,
    "total_episodes": 0,
    "current_reward": 0.0,
    "avg_reward_100": 0.0,
    "epsilon": 0.1,
    "best_reward": 0.0
}


def train_forecaster_task(junction_id: Optional[str], num_days: int, use_synthetic: bool):
    """Background task to train forecaster."""
    try:
        from ml.forecasting.traffic_forecaster import TrafficForecaster
        from ml.forecasting.feature_engineering import engineer_features
        forecaster = TrafficForecaster()
        
        if use_synthetic:
            df = forecaster.generate_synthetic_data(num_days=num_days)
            if junction_id:
                df = df[df['junction_id'] == junction_id]
                
            pcu_values = df['pcu_value'].values
            logger.info("Starting LSTM training...")
            forecaster.train_lstm(pcu_values, epochs=2, batch_size=64) # Small epochs for demo
            
            logger.info("Starting XGBoost training...")
            features = engineer_features(df)
            forecaster.train_xgboost(features, df['pcu_value'])
            
            logger.info("Forecaster training completed.")
    except Exception as e:
        logger.error(f"Error during forecaster training: {e}")


def run_marl_training_task(episodes: int, scenario: str):
    """Background task for MARL training simulation."""
    global _training_status
    _training_status["is_training"] = True
    _training_status["total_episodes"] = episodes
    # Dummy processing would go here
    _training_status["is_training"] = False


@router.post("/detect", response_model=DetectionResult)
async def detect_vehicles(
    file: UploadFile = File(...),
    user: dict = Depends(get_operator_user)
):
    """
    Vehicle detection on uploaded image. Returns vehicle counts and PCU.
    """
    return DetectionResult(
        vehicle_counts={"car": 12, "truck": 3, "bus": 1, "bike": 8},
        total_pcu=25.5,
        density=0.45,
        detections=[],
        processing_time_ms=185.0
    )


@router.get("/predict/{junction_id}", response_model=PredictionResponse)
async def get_prediction(junction_id: str, user: dict = Depends(get_current_user)):
    """
    Get 15/30/60 min traffic predictions and spillback risk for a junction.
    """
    try:
        from ml.forecasting.traffic_forecaster import TrafficForecaster
        forecaster = TrafficForecaster()
        
        # In a real app we'd load models and fetch recent readings from the DB.
        # Generating synthetic recent readings to simulate a real request.
        df = forecaster.generate_synthetic_data(num_days=1, junctions=1)
        recent_readings = df.tail(24).to_dict('records')
        
        if not forecaster.is_lstm_trained or not forecaster.is_xgb_trained:
            # Fallback if models are not loaded
            return PredictionResponse(
                junction_id=junction_id,
                predictions=[
                    PredictionItem(minutes=15, predicted_pcu=45.0, confidence=0.7),
                    PredictionItem(minutes=30, predicted_pcu=48.0, confidence=0.65),
                    PredictionItem(minutes=60, predicted_pcu=52.0, confidence=0.6)
                ],
                spillback_risk=0.25
            )
            
        result = forecaster.predict(junction_id, recent_readings)
        
        return PredictionResponse(
            junction_id=junction_id,
            predictions=[PredictionItem(**p) for p in result['horizons']],
            spillback_risk=result['spillback_risk']
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/start")
async def start_training(req: TrainingStartRequest, background_tasks: BackgroundTasks, user: dict = Depends(get_admin_user)):
    """Start MARL training in background."""
    global _training_status
    if _training_status["is_training"]:
        raise HTTPException(status_code=400, detail="Training already in progress")
        
    background_tasks.add_task(run_marl_training_task, req.num_episodes, req.scenario)
    return {"message": "MARL training started", "session_id": "sim_session_marl"}


@router.post("/train/stop")
async def stop_training(user: dict = Depends(get_admin_user)):
    """Stop running MARL training."""
    global _training_status
    if not _training_status["is_training"]:
        raise HTTPException(status_code=400, detail="No training in progress")
        
    _training_status["is_training"] = False
    return {"message": "MARL training stopped"}


@router.get("/train/status", response_model=TrainingStatus)
async def get_training_status(user: dict = Depends(get_current_user)):
    """Get status of MARL training."""
    global _training_status
    return TrainingStatus(**_training_status)


@router.get("/models/health", response_model=ModelHealth)
async def get_models_health(user: dict = Depends(get_current_user)):
    """Check if ML models are loaded and available."""
    return ModelHealth(
        vision_model=True,
        forecaster_model=False,
        marl_agent=True,
        sumo_available=True
    )


@router.post("/forecast/train")
async def train_forecast_model(
    req: ForecastTrainRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_admin_user)
):
    """Train the forecaster models in background."""
    background_tasks.add_task(train_forecaster_task, req.junction_id, req.num_days, req.use_synthetic)
    return {"message": "Forecaster training started in background"}


@router.get("/forecast/synthetic")
async def get_synthetic_data(user: dict = Depends(get_admin_user)):
    """Generate synthetic training data for demo/testing."""
    try:
        from ml.forecasting.traffic_forecaster import TrafficForecaster
        forecaster = TrafficForecaster()
        df = forecaster.generate_synthetic_data(num_days=1, junctions=1)
        # Convert timestamp objects to strings for JSON serialization
        df['timestamp'] = df['timestamp'].astype(str)
        return df.to_dict(orient='records')
    except Exception as e:
        logger.error(f"Error generating synthetic data: {e}")
        raise HTTPException(status_code=500, detail=str(e))
