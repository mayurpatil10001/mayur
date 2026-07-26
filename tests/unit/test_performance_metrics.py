"""
tests/unit/test_performance_metrics.py
========================================
Unit tests for pure performance metric calculations.
"""

import pytest
from backend.services.analytics.performance_calculator import (
    expectancy,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    sortino_ratio,
    win_rate,
)


def test_sharpe_ratio_zero_variance():
    """Constant PnL (zero standard deviation) should return None."""
    pnls = [100.0, 100.0, 100.0, 100.0]
    assert sharpe_ratio(pnls) is None


def test_profit_factor_no_losses():
    """All winning trades should return infinity for profit factor."""
    pnls = [50.0, 120.0, 80.0]
    assert profit_factor(pnls) == float("inf")


def test_max_drawdown_monotone_equity():
    """Monotonically increasing equity should have 0 max drawdown."""
    pnls = [10.0, 20.0, 30.0, 40.0]
    assert max_drawdown(pnls) == 0.0


def test_max_drawdown_calculation():
    """Test max drawdown on known equity curve peak to trough."""
    # Cum PnL: 100, 300, 200, 150, 400 -> Peak 300, Trough 150 -> DD 150
    pnls = [100.0, 200.0, -100.0, -50.0, 250.0]
    assert max_drawdown(pnls) == 150.0


def test_win_rate_empty():
    """Empty trade list returns None."""
    assert win_rate([]) is None
