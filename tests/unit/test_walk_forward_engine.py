"""
tests/unit/test_walk_forward_engine.py
========================================
Unit tests for WalkForwardEngine: dataset size guard and rolling fold calculations.
"""

import pytest
from backend.services.walkforward.walk_forward_engine import (
    WalkForwardEngine,
    WalkForwardSummary,
)


def test_insufficient_data_guard():
    """Engine should return 0 folds when total trading days < in_sample + out_of_sample."""
    engine = WalkForwardEngine(in_sample_days=252, out_of_sample_days=63)
    summary = engine.run([], account="TEST_ACC", symbol="FDAXM26")

    assert isinstance(summary, WalkForwardSummary)
    assert summary.n_folds == 0
    assert summary.total_oos_pnl == 0.0
    assert not summary.is_decay_detected
