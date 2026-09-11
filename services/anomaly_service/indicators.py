"""SN-086, SN-087, SN-088: Five Measured Anomaly Indicators
=============================================================
Computes anomaly indicators from canonical telemetry per link on rolling windows.
Baselines are measured from historical/rolling telemetry, never typed in.

Indicators:
1. SPEED_COLLAPSE (0.30): mean speed < 40% of rolling baseline over 60s window.
   Suppressed during normal red phase.
2. STATIONARY_VEHICLE (0.25): vehicle stopped > 20s outside signal queue.
   Suppressed during red signal or within queue context.
3. OCCUPANCY_SPIKE (0.20): lane occupancy > 0.75 absolute AND > 1.5x baseline over 60s.
4. FLOW_DROP (0.15): downstream link throughput < 50% of upstream over 120s.
5. QUEUE_ANOMALY (0.10): queue growth rate > 3x normal growth over 90s.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class IndicatorResult:
    indicator: str
    fired: bool
    measured_value: float
    threshold: float
    strength: float  # Clamped [0.0, 1.0]
    available: bool = True
    details: Optional[Dict[str, Any]] = None


def evaluate_speed_collapse(
    mean_speed_kmh: Optional[float],
    baseline_speed_kmh: float,
    controlling_signal_red: bool = False,
    is_normal_red_phase: bool = False,
) -> IndicatorResult:
    """SN-086: Indicator 1 — SPEED_COLLAPSE.

    Fires when mean speed < 40% of baseline over 60s window.
    Does NOT fire during normal red phase alternation.
    When speed is unresolvable (None), marks available=False.
    """
    if mean_speed_kmh is None:
        return IndicatorResult(
            indicator="SPEED_COLLAPSE",
            fired=False,
            measured_value=0.0,
            threshold=0.0,
            strength=0.0,
            available=False,
            details={"reason": "Speed not resolvable this window"},
        )

    if baseline_speed_kmh <= 0.0:
        return IndicatorResult(
            indicator="SPEED_COLLAPSE",
            fired=False,
            measured_value=round(mean_speed_kmh, 2),
            threshold=0.0,
            strength=0.0,
            available=False,
            details={"reason": "No baseline speed available"},
        )

    threshold = round(0.40 * baseline_speed_kmh, 2)

    # Normal red phase suppression: a normal cyclic red phase slows vehicles
    # temporarily, which is expected traffic dynamics, not an incident.
    if controlling_signal_red and is_normal_red_phase:
        return IndicatorResult(
            indicator="SPEED_COLLAPSE",
            fired=False,
            measured_value=round(mean_speed_kmh, 2),
            threshold=threshold,
            strength=0.0,
            available=True,
            details={"suppressed": True, "reason": "Normal cyclic red phase"},
        )

    fired = mean_speed_kmh < threshold
    strength = 0.0
    if fired and threshold > 0.0:
        # Strength: how far below the threshold the speed collapsed
        strength = min(1.0, max(0.0, (threshold - mean_speed_kmh) / threshold))

    return IndicatorResult(
        indicator="SPEED_COLLAPSE",
        fired=fired,
        measured_value=round(mean_speed_kmh, 2),
        threshold=threshold,
        strength=round(strength, 3),
        available=True,
        details={
            "baseline_speed_kmh": baseline_speed_kmh,
            "window_s": 60,
        },
    )


def evaluate_stationary_vehicle(
    max_stationary_s: float,
    in_queue_context: bool = False,
    controlling_signal_red: bool = False,
    data_source_available: bool = True,
) -> IndicatorResult:
    """SN-087: Indicator 2 — STATIONARY_VEHICLE.

    Fires when a vehicle is stopped > 20s outside signal queue.
    When neither SUMO vehicle state nor vision tracking is available,
    it does not fire and is marked available=False.
    Does NOT fire for queued vehicles at a red signal.
    """
    threshold = 20.0
    if not data_source_available:
        return IndicatorResult(
            indicator="STATIONARY_VEHICLE",
            fired=False,
            measured_value=0.0,
            threshold=threshold,
            strength=0.0,
            available=False,
            details={"reason": "Neither vehicle tracking nor SUMO vehicle state available"},
        )

    # Queue / red suppression
    if in_queue_context or controlling_signal_red:
        return IndicatorResult(
            indicator="STATIONARY_VEHICLE",
            fired=False,
            measured_value=round(max_stationary_s, 1),
            threshold=threshold,
            strength=0.0,
            available=True,
            details={"suppressed": True, "reason": "Vehicle within queue or red signal context"},
        )

    fired = max_stationary_s > threshold
    strength = 0.0
    if fired and threshold > 0.0:
        strength = min(1.0, max(0.0, (max_stationary_s - threshold) / threshold))

    return IndicatorResult(
        indicator="STATIONARY_VEHICLE",
        fired=fired,
        measured_value=round(max_stationary_s, 1),
        threshold=threshold,
        strength=round(strength, 3),
        available=True,
        details={"window_s": 60},
    )


def evaluate_occupancy_spike(
    measured_occupancy: float,
    baseline_occupancy: float,
) -> IndicatorResult:
    """SN-088: Indicator 3 — OCCUPANCY_SPIKE.

    Fires when occupancy > 0.75 absolute AND > 1.5x baseline (60s window).
    """
    # Threshold is 0.75 absolute AND 1.5x baseline
    relative_threshold = 1.5 * baseline_occupancy
    threshold = max(0.75, relative_threshold)

    fired = measured_occupancy > 0.75 and measured_occupancy > relative_threshold
    strength = 0.0
    if fired:
        # Per docs/14-incident-detection.md §3: strength = clamp((measured - threshold) / threshold, 0, 1)
        strength = min(1.0, max(0.0, (measured_occupancy - threshold) / threshold))

    return IndicatorResult(
        indicator="OCCUPANCY_SPIKE",
        fired=fired,
        measured_value=round(measured_occupancy, 2),
        threshold=round(threshold, 2),
        strength=round(strength, 3),
        available=True,
        details={
            "baseline_occupancy": round(baseline_occupancy, 2),
            "window_s": 60,
        },
    )


def evaluate_flow_drop(
    downstream_throughput: float,
    upstream_throughput: float,
) -> IndicatorResult:
    """SN-088: Indicator 4 — FLOW_DROP.

    Fires when downstream throughput < 50% of upstream throughput over 120s window.
    """
    if upstream_throughput <= 0.0:
        return IndicatorResult(
            indicator="FLOW_DROP",
            fired=False,
            measured_value=round(downstream_throughput, 1),
            threshold=0.0,
            strength=0.0,
            available=False,
            details={"reason": "No upstream throughput measurement"},
        )

    threshold = round(0.50 * upstream_throughput, 1)
    fired = downstream_throughput < threshold
    strength = 0.0
    if fired and threshold > 0.0:
        strength = min(1.0, max(0.0, (threshold - downstream_throughput) / threshold))

    return IndicatorResult(
        indicator="FLOW_DROP",
        fired=fired,
        measured_value=round(downstream_throughput, 1),
        threshold=threshold,
        strength=round(strength, 3),
        available=True,
        details={
            "upstream_throughput": upstream_throughput,
            "window_s": 120,
        },
    )


def evaluate_queue_anomaly(
    queue_growth_rate: float,
    normal_growth_rate: float,
) -> IndicatorResult:
    """SN-088: Indicator 5 — QUEUE_ANOMALY.

    Fires when queue growth rate > 3x normal growth rate for time of day over 90s window.
    """
    baseline_norm = max(normal_growth_rate, 0.5)
    threshold = round(3.0 * baseline_norm, 2)

    fired = queue_growth_rate > threshold
    strength = 0.0
    if fired and threshold > 0.0:
        strength = min(1.0, max(0.0, (queue_growth_rate - threshold) / threshold))

    return IndicatorResult(
        indicator="QUEUE_ANOMALY",
        fired=fired,
        measured_value=round(queue_growth_rate, 2),
        threshold=threshold,
        strength=round(strength, 3),
        available=True,
        details={
            "normal_growth_rate": normal_growth_rate,
            "window_s": 90,
        },
    )
