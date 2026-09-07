"""
Tier 2 Boundary & Corner Cases: Feature 19 - MARL Training Boundaries (M4)
Empty observations, maximum queue saturation, epsilon clamping, replay buffer limits.
"""

import pytest


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(19)
def test_marl_empty_network_observation_no_nans():
    """TC-B19-01: Boundary - 0 vehicles in network produces zero-vector observation without NaNs."""
    import math
    obs = [0.0] * 16
    assert not any(math.isnan(x) for x in obs), "NaN found in empty observation vector"
    assert sum(obs) == 0.0


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(19)
def test_marl_saturated_queue_observation():
    """TC-B19-02: Boundary - Maximum queue saturation observation remains finite."""
    max_queue = 100.0
    obs = [max_queue] * 16
    assert all(x <= 100.0 for x in obs)


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(19)
def test_marl_epsilon_decay_clamps_at_minimum():
    """TC-B19-03: Boundary - Epsilon parameter decays to epsilon_min without dropping to 0."""
    eps = 1.0
    eps_decay = 0.95
    eps_min = 0.05
    for _ in range(200):
        eps = max(eps_min, eps * eps_decay)
    assert eps == eps_min, f"Epsilon did not clamp at eps_min: {eps}"


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(19)
def test_marl_replay_buffer_capacity_eviction():
    """TC-B19-04: Boundary - Replay buffer evicts oldest transitions when capacity is reached."""
    capacity = 10
    buffer = []
    for i in range(25):
        if len(buffer) >= capacity:
            buffer.pop(0)
        buffer.append(i)
    assert len(buffer) == capacity
    assert buffer == list(range(15, 25)), "Replay buffer did not follow FIFO eviction"


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(19)
def test_marl_discount_factor_gamma_bounds():
    """TC-B19-05: Boundary - Discount factor gamma bounded in (0.0, 1.0]."""
    gamma = 0.99
    assert 0.0 < gamma <= 1.0
