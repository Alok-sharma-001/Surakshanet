from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class DetectionRequest(BaseModel):
    # Empty schema since we receive multipart form data
    pass

class DetectionResult(BaseModel):
    vehicle_counts: Dict[str, int]
    total_pcu: float
    density: Optional[float] = None
    detections: List[Dict[str, Any]]
    processing_time_ms: float

class PredictionItem(BaseModel):
    minutes: int
    predicted_pcu: float
    confidence: float

class PredictionResponse(BaseModel):
    junction_id: str
    predictions: List[PredictionItem]
    spillback_risk: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class TrainingStatus(BaseModel):
    is_training: bool
    episode: int
    total_episodes: int
    current_reward: float
    avg_reward_100: float
    epsilon: float
    best_reward: float
    last_trained: Optional[str] = "2026-09-04T10:00:00Z"

class TrainingStartRequest(BaseModel):
    num_episodes: int = 500
    scenario: str = 'morning_peak'

class ModelHealth(BaseModel):
    status: str = "healthy"
    vision_model: bool
    forecaster_model: bool
    marl_agent: bool
    sumo_available: bool

class ForecastTrainRequest(BaseModel):
    junction_id: Optional[str] = None
    num_days: int = 7
    use_synthetic: bool = True
