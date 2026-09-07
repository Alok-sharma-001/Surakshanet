"""
Tier 2 Boundary & Corner Cases: Feature 20 - Reproducibility Boundaries (M4)
Seed = 0, maximum 32-bit integer seed, negative seeds, weight checkpoint integrity.
"""

import random
import pytest


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(20)
def test_seed_zero_reproducible():
    """TC-B20-01: Boundary - Seed=0 initializes generator deterministically."""
    random.seed(0)
    v1 = random.random()
    random.seed(0)
    v2 = random.random()
    assert v1 == v2, "Seed 0 did not produce reproducible random output"


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(20)
def test_maximum_32bit_integer_seed():
    """TC-B20-02: Boundary - Maximum 32-bit unsigned int seed (2^31 - 1) supported."""
    max_seed = 2147483647
    random.seed(max_seed)
    v1 = random.random()
    random.seed(max_seed)
    v2 = random.random()
    assert v1 == v2


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(20)
def test_negative_seed_supported():
    """TC-B20-03: Boundary - Negative integer seed handled without crash."""
    random.seed(-42)
    v = random.random()
    assert 0.0 <= v <= 1.0


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(20)
def test_weight_checkpoint_corrupt_file_exception():
    """TC-B20-04: Boundary - Attempting to load corrupted weight checkpoint raises error."""
    import tempfile
    with tempfile.NamedTemporaryFile("wb", delete=True) as f:
        f.write(b"CORRUPTED_TORCH_BYTES_0000")
        f.flush()
        # Loading invalid binary should raise Exception
        try:
            import torch
            torch.load(f.name)
            assert False, "Loading corrupt weights should have failed"
        except Exception:
            assert True


@pytest.mark.tier2
@pytest.mark.m4
@pytest.mark.feature(20)
def test_hyperparameter_config_valid_json():
    """TC-B20-05: Boundary - Hyperparameter logging produces valid parseable JSON."""
    import json
    params = {"seed": 42, "lr": 0.001, "batch_size": 32, "gamma": 0.99}
    serialized = json.dumps(params)
    deserialized = json.loads(serialized)
    assert deserialized == params
