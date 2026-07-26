"""
tests/unit/test_time_bin_analyzer.py
======================================
Unit tests for TimeBinAnalyzer: BH-FDR correction, min_trades guard, and single slot edge cases.
"""

import pytest
from backend.services.analytics.time_bin_analyzer import (
    TimeBinAnalyzer,
    TimeBinMetrics,
    TradeSummary,
    benjamini_hochberg,
)
from datetime import datetime, timezone


def test_benjamini_hochberg_correction():
    """Verify BH-FDR step-up correction logic."""
    raw_pvalues = [0.001, 0.01, 0.04, 0.20, 0.50]
    adjusted = benjamini_hochberg(raw_pvalues, alpha=0.05)

    assert len(adjusted) == len(raw_pvalues)
    # Adjusted p-values must be monotonically non-decreasing when sorted by raw p-value
    assert adjusted[0] <= adjusted[1] <= adjusted[2]
    assert adjusted[0] < 0.05


def test_min_trades_guard():
    """Slots with fewer than min_trades should not be promoted regardless of p-value."""
    trades = [
        TradeSummary(
            account_name="ACC1",
            symbol="FDAXM26",
            time_slot_ny="09:30",
            realized_pnl=100.0,
            entry_time=datetime.now(timezone.utc),
        )
        for _ in range(5)  # Only 5 trades < min_trades (30)
    ]

    analyzer = TimeBinAnalyzer(alpha=0.05, min_trades=30)
    grid = analyzer.analyze(trades)

    for m in grid.values():
        assert not m.is_promoted


def test_single_trade_slot_exclusion():
    """Single trade in a slot should not trigger Wilcoxon or promotion."""
    trades = [
        TradeSummary(
            account_name="ACC1",
            symbol="FDAXM26",
            time_slot_ny="10:00",
            realized_pnl=500.0,
            entry_time=datetime.now(timezone.utc),
        )
    ]

    analyzer = TimeBinAnalyzer(alpha=0.05, min_trades=30)
    grid = analyzer.analyze(trades)

    slot_key = "ACC1|FDAXM26|10:00"
    assert slot_key in grid
    assert not grid[slot_key].is_promoted
    assert grid[slot_key].trade_count == 1
