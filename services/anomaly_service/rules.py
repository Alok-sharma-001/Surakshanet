"""SN-089: Fixed Combination Rule and Anomaly Score
===================================================
Formula per docs/14-incident-detection.md §3:
  confidence = Σ (weight_i * strength_i) / Σ (weight_i for available indicators)
  strength_i = clamp((measured_i - threshold_i) / threshold_i, 0, 1)

Weights:
  SPEED_COLLAPSE:      0.30
  STATIONARY_VEHICLE:  0.25
  OCCUPANCY_SPIKE:     0.20
  FLOW_DROP:           0.15
  QUEUE_ANOMALY:       0.10

Incident raised when:
  indicators_fired >= 2  AND  confidence >= 0.50

Label: "anomaly score", NOT a crash probability.
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from services.anomaly_service.indicators import IndicatorResult

INDICATOR_WEIGHTS: Dict[str, float] = {
    "SPEED_COLLAPSE": 0.30,
    "STATIONARY_VEHICLE": 0.25,
    "OCCUPANCY_SPIKE": 0.20,
    "FLOW_DROP": 0.15,
    "QUEUE_ANOMALY": 0.10,
}

MIN_INDICATORS_FIRED = 2
MIN_CONFIDENCE_THRESHOLD = 0.50


@dataclass
class AnomalyEvaluation:
    should_raise: bool
    confidence: float  # Anomaly score between 0.0 and 1.0
    indicators_fired: int
    indicators_total: int
    fired_indicators: List[IndicatorResult]
    all_indicators: List[IndicatorResult]
    note: str
    incident_type: str = "POSSIBLE_INCIDENT"
    status: str = "UNVERIFIED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_type": self.incident_type,
            "status": self.status,
            "confidence": self.confidence,
            "indicators_fired": self.indicators_fired,
            "indicators_total": self.indicators_total,
            "indicators": [
                {
                    "indicator": ind.indicator,
                    "measured_value": ind.measured_value,
                    "threshold": ind.threshold,
                }
                for ind in self.fired_indicators
            ],
            "note": self.note,
        }


def evaluate_anomaly_combination(results: List[IndicatorResult]) -> AnomalyEvaluation:
    """Evaluates the combination rule over measured indicator results.

    The formula is fixed and documented:
    - Never tunes thresholds after the fact.
    - Confidence is normalized by available indicators.
    - Anomaly is raised strictly when indicators_fired >= 2 AND confidence >= 0.50.
    """
    available = [r for r in results if r.available]
    fired = [r for r in available if r.fired]

    if not available:
        return AnomalyEvaluation(
            should_raise=False,
            confidence=0.0,
            indicators_fired=0,
            indicators_total=0,
            fired_indicators=[],
            all_indicators=results,
            note="Possible incident. Unverified — operator review required.",
        )

    available_weight_sum = sum(INDICATOR_WEIGHTS.get(r.indicator, 0.0) for r in available)
    if available_weight_sum <= 0.0:
        available_weight_sum = 1.0

    weighted_strength_sum = sum(
        INDICATOR_WEIGHTS.get(r.indicator, 0.0) * r.strength for r in fired
    )

    confidence = min(1.0, max(0.0, weighted_strength_sum / available_weight_sum))
    confidence = round(confidence, 2)

    should_raise = len(fired) >= MIN_INDICATORS_FIRED and confidence >= MIN_CONFIDENCE_THRESHOLD

    return AnomalyEvaluation(
        should_raise=should_raise,
        confidence=confidence,
        indicators_fired=len(fired),
        indicators_total=len(available),
        fired_indicators=fired,
        all_indicators=results,
        note="Possible incident. Unverified — operator review required.",
    )
