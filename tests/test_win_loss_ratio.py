"""
Unit tests for win/loss ratio, payoff-adjusted expectancy, and risk flag calculations in PerformanceMetricsCalculator.

Run with:
    pytest tests/test_win_loss_ratio.py -v
"""

from datetime import datetime, timedelta
import pytest
from typing import List

from trading_platform.models.trading import ProcessedTrade
from trading_platform.services.performance_metrics_calculator import (
    PerformanceMetricsCalculator,
)


def _make_trade(pnl: float, minutes_offset: int = 0) -> ProcessedTrade:
    """Helper to generate dummy trade."""
    entry = datetime(2024, 1, 1, 9, 30) + timedelta(minutes=minutes_offset)
    exit = entry + timedelta(minutes=15)
    side = 'LONG' if pnl >= 0 else 'SHORT'
    entry_p = 15000.0
    exit_p = entry_p + pnl if side == 'LONG' else entry_p - pnl
    return ProcessedTrade(
        trade_id=f"trade_{minutes_offset}",
        account_name="TM_7",
        symbol="NQ",
        entry_time=entry,
        exit_time=exit,
        entry_price=entry_p,
        exit_price=exit_p,
        quantity=1,
        side=side,
        profit_loss=pnl,
        commission=0.0,
        duration_minutes=15,
        hour_of_day=entry.hour,
        day_of_week=entry.weekday(),
        entry_order_id=f"ord_in_{minutes_offset}",
        exit_order_id=f"ord_out_{minutes_offset}",
    )


def test_normal_profitable_account():
    """WLR > 1.0, risk_flag = False."""
    trades = [
        _make_trade(200.0, 0),
        _make_trade(200.0, 30),
        _make_trade(-100.0, 60),
    ]
    calc = PerformanceMetricsCalculator()
    metrics = calc.calculate_performance_metrics(trades, "TM_7", "NQ")

    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert pytest.approx(metrics.win_rate, 0.001) == 2 / 3
    assert metrics.average_win == 200.0
    assert metrics.average_loss == -100.0
    assert metrics.win_loss_ratio == 2.0  # 200 / 100
    assert pytest.approx(metrics.payoff_adjusted_expectancy, 0.01) == (2/3)*200 + (1/3)*(-100)
    assert metrics.risk_flag is False


def test_high_win_rate_trap_tm7_pattern():
    """Win rate > 55% but WLR < 1.0 -> risk_flag = True."""
    # 6 wins of $50, 4 losses of $100 -> Win rate = 60%, WLR = 50/100 = 0.5
    trades = [_make_trade(50.0, i*30) for i in range(6)] + [
        _make_trade(-100.0, (i+6)*30) for i in range(4)
    ]
    calc = PerformanceMetricsCalculator()
    metrics = calc.calculate_performance_metrics(trades, "TM_7", "NQ")

    assert metrics.win_rate == 0.60
    assert metrics.average_win == 50.0
    assert metrics.average_loss == -100.0
    assert metrics.win_loss_ratio == 0.5
    assert metrics.risk_flag is True


def test_100_percent_win_rate():
    """No losing trades -> WLR = None, risk_flag = False."""
    trades = [_make_trade(100.0, i*30) for i in range(5)]
    calc = PerformanceMetricsCalculator()
    metrics = calc.calculate_performance_metrics(trades, "TM_7", "NQ")

    assert metrics.win_rate == 1.0
    assert metrics.win_loss_ratio is None
    assert metrics.payoff_adjusted_expectancy == 100.0
    assert metrics.risk_flag is False


def test_0_percent_win_rate():
    """No winning trades -> WLR = None or 0.0, risk_flag = False."""
    trades = [_make_trade(-100.0, i*30) for i in range(5)]
    calc = PerformanceMetricsCalculator()
    metrics = calc.calculate_performance_metrics(trades, "TM_7", "NQ")

    assert metrics.win_rate == 0.0
    assert metrics.win_loss_ratio is None
    assert metrics.payoff_adjusted_expectancy == -100.0
    assert metrics.risk_flag is False


def test_risk_flag_boundaries():
    """Boundary testing for risk_flag (win_rate > 0.55 and WLR < 1.0)."""
    calc = PerformanceMetricsCalculator()

    # Case A: Win rate = 50% (<= 55%), WLR = 0.5 -> risk_flag = False
    trades_a = [_make_trade(50.0, i*30) for i in range(5)] + [
        _make_trade(-100.0, (i+5)*30) for i in range(5)
    ]
    metrics_a = calc.calculate_performance_metrics(trades_a, "TM_7", "NQ")
    assert metrics_a.win_rate == 0.50
    assert metrics_a.win_loss_ratio == 0.5
    assert metrics_a.risk_flag is False

    # Case B: Win rate = 60% (> 55%), WLR = 1.0 (>= 1.0) -> risk_flag = False
    trades_b = [_make_trade(100.0, i*30) for i in range(6)] + [
        _make_trade(-100.0, (i+6)*30) for i in range(4)
    ]
    metrics_b = calc.calculate_performance_metrics(trades_b, "TM_7", "NQ")
    assert metrics_b.win_rate == 0.60
    assert metrics_b.win_loss_ratio == 1.0
    assert metrics_b.risk_flag is False
