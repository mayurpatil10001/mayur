"""
backend/services/analytics/performance_calculator.py
=====================================================
Pure functions for all trading performance metrics.
All functions handle empty / insufficient input gracefully (return None or 0.0).
No database access — caller provides trade PnL lists.
"""

import math
from typing import Sequence


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator


# ── Core Metrics ──────────────────────────────────────────────────────────────

def win_rate(pnls: Sequence[float]) -> float | None:
    """Fraction of trades with PnL > 0. Returns None if no trades."""
    if not pnls:
        return None
    wins = sum(1 for p in pnls if p > 0)
    return wins / len(pnls)


def profit_factor(pnls: Sequence[float]) -> float | None:
    """Gross profit / Gross loss. Returns None if no losing trades."""
    if not pnls:
        return None
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else None
    return gross_profit / gross_loss


def expectancy(pnls: Sequence[float]) -> float | None:
    """
    Expected value per trade = (win_rate * avg_win) - (loss_rate * avg_loss).
    Returns None if fewer than 2 trades.
    """
    if len(pnls) < 2:
        return None
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    wr = len(wins) / len(pnls)
    lr = len(losses) / len(pnls)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    return (wr * avg_win) - (lr * avg_loss)


def max_drawdown(pnls: Sequence[float]) -> float:
    """
    Maximum peak-to-trough drawdown of cumulative PnL series.
    Returns drawdown as a positive number (i.e., the magnitude).
    """
    if not pnls:
        return 0.0
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for p in pnls:
        cumulative += p
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd
    return max_dd


def max_drawdown_pct(pnls: Sequence[float], initial_equity: float = 100_000.0) -> float:
    """Max drawdown as fraction of initial equity."""
    dd = max_drawdown(pnls)
    return _safe_divide(dd, initial_equity + max(0.0, sum(pnls)), default=0.0)


def sharpe_ratio(pnls: Sequence[float], rf: float = 0.0, periods_per_year: int = 252) -> float | None:
    """
    Annualized Sharpe Ratio = (mean_return - rf) / std_return * sqrt(periods_per_year).
    Returns None if fewer than 2 trades or zero standard deviation.
    """
    if len(pnls) < 2:
        return None
    mean = sum(pnls) / len(pnls)
    variance = sum((p - mean) ** 2 for p in pnls) / (len(pnls) - 1)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return (mean - rf) / std * math.sqrt(periods_per_year)


def sortino_ratio(pnls: Sequence[float], rf: float = 0.0, periods_per_year: int = 252) -> float | None:
    """
    Annualized Sortino Ratio = (mean_return - rf) / downside_std * sqrt(periods_per_year).
    Uses only negative returns for downside deviation.
    Returns None if fewer than 2 trades or no negative returns.
    """
    if len(pnls) < 2:
        return None
    mean = sum(pnls) / len(pnls)
    negative = [p for p in pnls if p < rf]
    if len(negative) < 2:
        return None
    downside_var = sum((p - rf) ** 2 for p in negative) / len(negative)
    downside_std = math.sqrt(downside_var)
    if downside_std == 0:
        return None
    return (mean - rf) / downside_std * math.sqrt(periods_per_year)


def calmar_ratio(pnls: Sequence[float], periods_per_year: int = 252) -> float | None:
    """
    Calmar Ratio = Annualized Net PnL / Max Drawdown.
    Returns None if max drawdown is zero or fewer than 2 trades.
    """
    if len(pnls) < 2:
        return None
    dd = max_drawdown(pnls)
    if dd == 0:
        return None
    annualized_pnl = sum(pnls) / len(pnls) * periods_per_year
    return annualized_pnl / dd


def net_pnl(pnls: Sequence[float]) -> float:
    return sum(pnls)


def avg_trade_pnl(pnls: Sequence[float]) -> float | None:
    if not pnls:
        return None
    return sum(pnls) / len(pnls)


def largest_win(pnls: Sequence[float]) -> float | None:
    wins = [p for p in pnls if p > 0]
    return max(wins) if wins else None


def largest_loss(pnls: Sequence[float]) -> float | None:
    losses = [p for p in pnls if p < 0]
    return min(losses) if losses else None


def consecutive_wins(pnls: Sequence[float]) -> int:
    """Maximum consecutive winning trades."""
    max_streak = current = 0
    for p in pnls:
        if p > 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


def consecutive_losses(pnls: Sequence[float]) -> int:
    """Maximum consecutive losing trades."""
    max_streak = current = 0
    for p in pnls:
        if p < 0:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 0
    return max_streak


# ── Composite Snapshot ────────────────────────────────────────────────────────

def full_performance_snapshot(
    pnls: Sequence[float],
    trade_count: int | None = None,
    rf: float = 0.0,
) -> dict:
    """
    Compute all performance metrics from a PnL list.
    Returns a dict safe for JSON serialization (no None keys omitted).
    """
    pnls_list = list(pnls)
    n = trade_count if trade_count is not None else len(pnls_list)

    wins = [p for p in pnls_list if p > 0]
    losses = [p for p in pnls_list if p < 0]

    return {
        "trade_count": n,
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": win_rate(pnls_list),
        "net_pnl": net_pnl(pnls_list),
        "gross_profit": sum(wins),
        "gross_loss": abs(sum(losses)),
        "profit_factor": profit_factor(pnls_list),
        "expectancy": expectancy(pnls_list),
        "avg_trade_pnl": avg_trade_pnl(pnls_list),
        "max_drawdown": max_drawdown(pnls_list),
        "sharpe_ratio": sharpe_ratio(pnls_list, rf=rf),
        "sortino_ratio": sortino_ratio(pnls_list, rf=rf),
        "calmar_ratio": calmar_ratio(pnls_list),
        "largest_win": largest_win(pnls_list),
        "largest_loss": largest_loss(pnls_list),
        "max_consecutive_wins": consecutive_wins(pnls_list),
        "max_consecutive_losses": consecutive_losses(pnls_list),
    }
