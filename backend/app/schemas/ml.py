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
    """
    MARL training state.

    SN-001/SN-003: every metric is optional and defaults to None. The previous
    shape required them and defaulted `last_trained` to a hardcoded timestamp,
    which meant the endpoint could not express "no training data" -- it had to
    return numbers whether or not any existed.
    """
    status: str = "unavailable"          # "unavailable" | "running" | "complete"
    reason: Optional[str] = None         # why, when status is "unavailable"
    is_training: bool = False
    episode: Optional[int] = None
    total_episodes: Optional[int] = None
    current_reward: Optional[float] = None
    avg_reward_100: Optional[float] = None
    epsilon: Optional[float] = None
    best_reward: Optional[float] = None
    last_trained: Optional[str] = None


class TrainingStartRequest(BaseModel):
    num_episodes: int = 500
    episodes: Optional[int] = None
    seed: Optional[int] = 42
    scenario: str = 'morning_peak'

    def model_post_init(self, __context):
        if self.episodes is not None:
            self.num_episodes = self.episodes


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
