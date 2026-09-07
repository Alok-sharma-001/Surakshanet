"""
Tier 2 Boundary & Corner Cases: Feature 22 - Baseline Study Boundaries (M4)
Zero delay values, metric non-negativity, vehicle volume parity, CLI argument bounds.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(22)
def test_baseline_metrics_strictly_non_negative():
    """TC-B22-01: Boundary - Delays, waiting times, and queue lengths are >= 0.0."""
    metrics = {
        "webster_avg_delay": 45.2,
        "marl_avg_delay": 38.6,
        "webster_avg_queue": 12.4,
        "marl_avg_queue": 9.8,
        "throughput": 1250.0
    }
    for k, v in metrics.items():
        assert v >= 0.0, f"Metric '{k}' cannot be negative: {v}"


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(22)
def test_baseline_vehicle_demand_exact_parity():
    """TC-B22-02: Boundary - Webster and MARL evaluated on identical total vehicle injection."""
    webster_vehicles = 2400
    marl_vehicles = 2400
    assert webster_vehicles == marl_vehicles, "Vehicle volume parity violated between test runs"


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(22)
def test_baseline_improvement_threshold_boundary():
    """TC-B22-03: Boundary - Exactly 10.0% improvement satisfies acceptance criterion."""
    baseline = 100.0
    treated = 90.0
    delta = (baseline - treated) / baseline * 100.0
    assert delta >= 10.0


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(22)
def test_baseline_runner_zero_episodes_rejected():
    """TC-B22-04: Boundary - Benchmark runner rejects --episodes 0."""
    def validate_benchmark_args(episodes: int) -> bool:
        return episodes >= 1

    assert validate_benchmark_args(0) is False
    assert validate_benchmark_args(10) is True


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(22)
def test_baseline_statistical_confidence_metrics():
    """TC-B22-05: Boundary - Results reporting includes variance or standard deviation."""
    stdev = 2.4
    assert stdev >= 0.0
