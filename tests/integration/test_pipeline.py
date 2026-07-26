"""
tests/integration/test_pipeline.py
====================================
Integration test for full data pipeline: parse -> BH-FDR gate -> Trade queries.
"""

import pytest
from backend.services.analytics.performance_calculator import full_performance_snapshot
from backend.services.analytics.time_bin_analyzer import TimeBinAnalyzer, TradeSummary
from datetime import datetime, timezone


def test_full_analytics_pipeline():
    """Verify flow from raw trade summaries through time-bin analyzer and performance calculator."""
    trades = [
        TradeSummary(
            account_name="TM_7",
            symbol="FDAXM26",
            time_slot_ny="09:30",
            realized_pnl=150.0 if i % 2 == 0 else -50.0,
            entry_time=datetime.now(timezone.utc),
        )
        for i in range(40)
    ]

    analyzer = TimeBinAnalyzer(alpha=0.05, min_trades=30)
    grid = analyzer.analyze(trades)

    assert len(grid) == 1
    slot = grid["TM_7|FDAXM26|09:30"]
    assert slot.trade_count == 40
    assert slot.win_count == 20
    assert slot.loss_count == 20

    pnls = [t.realized_pnl for t in trades]
    snap = full_performance_snapshot(pnls)
    assert snap["trade_count"] == 40
    assert snap["net_pnl"] == 2000.0  # 20 * 150 - 20 * 50
