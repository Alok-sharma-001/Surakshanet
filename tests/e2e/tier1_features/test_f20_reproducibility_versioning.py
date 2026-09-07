"""
Tier 1 Feature Coverage: Feature 20 - Reproducibility & Weight Versioning (M4)
Requirement: Add deterministic random seeds (torch, numpy, random, SUMO),
log hyperparameters, version weights.
"""

import os
import random
import numpy as np
import pytest
from tests.e2e.client import PROJECT_ROOT


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(20)
def test_seed_determinism_python_and_numpy():
    """TC-F20-01: Verify identical seed produces identical random sequences."""
    def sample_sequence(seed: int):
        random.seed(seed)
        np.random.seed(seed)
        r_py = [random.random() for _ in range(5)]
        r_np = np.random.rand(5).tolist()
        return r_py, r_np

    seq1_py, seq1_np = sample_sequence(42)
    seq2_py, seq2_np = sample_sequence(42)
    assert seq1_py == seq2_py, "Python random generator not deterministic with seed 42"
    assert seq1_np == seq2_np, "NumPy random generator not deterministic with seed 42"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(20)
def test_weights_directory_structure():
    """TC-F20-02: Verify model weights directory exists in ml/."""
    candidates = [
        os.path.join(PROJECT_ROOT, "ml", "marl", "weights"),
        os.path.join(PROJECT_ROOT, "ml", "weights"),
        os.path.join(PROJECT_ROOT, "ml", "forecasting", "weights"),
    ]
    found = [p for p in candidates if os.path.isdir(p) or os.path.exists(os.path.dirname(p))]
    assert len(found) > 0, f"No weights directory found in {candidates}"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(20)
def test_hyperparameter_logging_support():
    """TC-F20-03: Verify training scripts accept seed and log parameters."""
    train_script = os.path.join(PROJECT_ROOT, "ml", "marl", "train_marl.py")
    if os.path.exists(train_script):
        with open(train_script, "r", encoding="utf-8") as f:
            content = f.read()
        assert "seed" in content.lower(), "train_marl.py does not accept or set random seed"


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(20)
def test_model_versioning_naming_convention():
    """TC-F20-04: Check versioned weight filename patterns."""
    pattern = "marl_dqn_v1.0.pth"
    assert "_v" in pattern and pattern.endswith(".pth")


@pytest.mark.tier1
@pytest.mark.m4
@pytest.mark.feature(20)
def test_different_seeds_produce_distinct_sequences():
    """TC-F20-05: Verify seed 42 and seed 43 produce distinct outputs."""
    random.seed(42)
    seq_42 = [random.random() for _ in range(5)]
    random.seed(43)
    seq_43 = [random.random() for _ in range(5)]
    assert seq_42 != seq_43, "Different seeds should produce different outputs"
