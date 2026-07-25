"""
backend/services/walkforward/walk_forward_engine.py
====================================================
Walk-forward validation engine.

Rolling window approach:
  - in_sample: 252 trading days (configurable)
  - out_of_sample: 63 trading days (configurable)
  - step: advances by out_of_sample days each fold

For each fold:
  1. Select IS trades, run BH-FDR to find promoted time slots
  2. Filter OOS trades to promoted slots only
  3. Compute OOS performance metrics
  4. Record fold result

Aggregate all folds → WalkForwardSummary with decay detection.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Sequence

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    """Minimal trade data needed for walk-forward analysis."""
    account_name: str
    symbol: str
    session_date: str          # "YYYY-MM-DD"
    time_slot_ny: str          # "HH:MM"
    realized_pnl: float
    entry_time: datetime


@dataclass
class FoldResult:
    """Results for a single walk-forward fold."""
    fold_index: int
    is_start: str              # YYYY-MM-DD
    is_end: str
    oos_start: str
    oos_end: str

    # In-sample stats
    is_trade_count: int = 0
    is_promoted_slots: list[str] = field(default_factory=list)

    # Out-of-sample stats
    oos_trade_count: int = 0
    oos_total_pnl: float = 0.0
    oos_win_rate: float | None = None
    oos_sharpe: float | None = None
    oos_sortino: float | None = None
    oos_max_drawdown: float | None = None
    oos_profit_factor: float | None = None
    oos_expectancy: float | None = None


@dataclass
class WalkForwardSummary:
    """Aggregated results across all walk-forward folds."""
    account_name: str
    symbol: str
    n_folds: int
    in_sample_days: int
    out_of_sample_days: int
    folds: list[FoldResult] = field(default_factory=list)

    # Aggregated OOS metrics
    total_oos_pnl: float = 0.0
    avg_oos_sharpe: float | None = None
    avg_oos_drawdown: float | None = None
    avg_oos_win_rate: float | None = None
    avg_oos_profit_factor: float | None = None

    # Decay analysis
    is_decay_detected: bool = False
    decay_slope: float | None = None   # Linear regression slope of OOS PnL per fold
    decay_r_squared: float | None = None


class WalkForwardEngine:
    """
    Runs rolling walk-forward validation with BH-FDR slot promotion.

    Usage:
        engine = WalkForwardEngine(in_sample_days=252, out_of_sample_days=63)
        summary = engine.run(trades, account="TM_7", symbol="FDAXM26")
    """

    def __init__(
        self,
        in_sample_days: int = 252,
        out_of_sample_days: int = 63,
        step_days: int | None = None,
        bh_alpha: float = 0.05,
        min_trades_per_slot: int = 30,
    ) -> None:
        self.in_sample_days = in_sample_days
        self.out_of_sample_days = out_of_sample_days
        self.step_days = step_days or out_of_sample_days
        self.bh_alpha = bh_alpha
        self.min_trades_per_slot = min_trades_per_slot

    def run(
        self,
        trades: Sequence[TradeRecord],
        account: str,
        symbol: str,
    ) -> WalkForwardSummary:
        """
        Execute walk-forward validation for one (account, symbol) pair.

        Args:
            trades: All trades for this account/symbol, any order.
            account: Account name (for summary metadata).
            symbol: Symbol name.

        Returns:
            WalkForwardSummary with per-fold results and aggregate metrics.
        """
        from backend.services.analytics.time_bin_analyzer import TimeBinAnalyzer, TradeSummary
        from backend.services.analytics.performance_calculator import (
            full_performance_snapshot,
        )

        # Filter to this account/symbol and sort by date
        relevant = [
            t for t in trades
            if t.account_name == account and t.symbol == symbol
        ]
        relevant.sort(key=lambda t: t.session_date)

        if not relevant:
            logger.warning(f"WalkForward: No trades found for {account}/{symbol}")
            return WalkForwardSummary(
                account_name=account, symbol=symbol,
                n_folds=0, in_sample_days=self.in_sample_days,
                out_of_sample_days=self.out_of_sample_days,
            )

        # Get unique trading dates
        all_dates = sorted({t.session_date for t in relevant})
        if len(all_dates) < self.in_sample_days + self.out_of_sample_days:
            logger.warning(
                f"WalkForward: Only {len(all_dates)} trading days available for "
                f"{account}/{symbol} — need at least "
                f"{self.in_sample_days + self.out_of_sample_days}. Skipping."
            )
            return WalkForwardSummary(
                account_name=account, symbol=symbol,
                n_folds=0, in_sample_days=self.in_sample_days,
                out_of_sample_days=self.out_of_sample_days,
            )

        # Build date lookup for fast slicing
        date_to_trades: dict[str, list[TradeRecord]] = {}
        for t in relevant:
            date_to_trades.setdefault(t.session_date, []).append(t)

        analyzer = TimeBinAnalyzer(
            alpha=self.bh_alpha,
            min_trades=self.min_trades_per_slot,
        )
        folds: list[FoldResult] = []

        # Rolling window
        window_start = 0
        fold_idx = 0

        while True:
            is_start_idx = window_start
            is_end_idx = window_start + self.in_sample_days - 1
            oos_start_idx = is_end_idx + 1
            oos_end_idx = oos_start_idx + self.out_of_sample_days - 1

            if oos_end_idx >= len(all_dates):
                break

            is_dates = set(all_dates[is_start_idx:is_end_idx + 1])
            oos_dates = set(all_dates[oos_start_idx:oos_end_idx + 1])

            is_trades = [t for t in relevant if t.session_date in is_dates]
            oos_trades = [t for t in relevant if t.session_date in oos_dates]

            # Run BH-FDR on in-sample
            is_summaries = [
                TradeSummary(
                    account_name=t.account_name,
                    symbol=t.symbol,
                    time_slot_ny=t.time_slot_ny,
                    realized_pnl=t.realized_pnl,
                    entry_time=t.entry_time,
                )
                for t in is_trades
            ]
            grid = analyzer.analyze(is_summaries)
            promoted_slots = {
                m.time_slot_ny for m in grid.values() if m.is_promoted
            }

            # Apply promoted slots to OOS
            oos_promoted = [t for t in oos_trades if t.time_slot_ny in promoted_slots]
            oos_pnls = [t.realized_pnl for t in oos_promoted]

            snap = full_performance_snapshot(oos_pnls) if oos_pnls else {}

            fold = FoldResult(
                fold_index=fold_idx,
                is_start=all_dates[is_start_idx],
                is_end=all_dates[is_end_idx],
                oos_start=all_dates[oos_start_idx],
                oos_end=all_dates[oos_end_idx],
                is_trade_count=len(is_trades),
                is_promoted_slots=sorted(promoted_slots),
                oos_trade_count=len(oos_promoted),
                oos_total_pnl=snap.get("net_pnl", 0.0),
                oos_win_rate=snap.get("win_rate"),
                oos_sharpe=snap.get("sharpe_ratio"),
                oos_sortino=snap.get("sortino_ratio"),
                oos_max_drawdown=snap.get("max_drawdown"),
                oos_profit_factor=snap.get("profit_factor"),
                oos_expectancy=snap.get("expectancy"),
            )
            folds.append(fold)

            logger.debug(
                f"Fold {fold_idx}: IS={len(is_trades)} trades, "
                f"{len(promoted_slots)} promoted slots, "
                f"OOS={len(oos_promoted)} trades, PnL={fold.oos_total_pnl:.0f}"
            )

            window_start += self.step_days
            fold_idx += 1

        summary = WalkForwardSummary(
            account_name=account,
            symbol=symbol,
            n_folds=len(folds),
            in_sample_days=self.in_sample_days,
            out_of_sample_days=self.out_of_sample_days,
            folds=folds,
        )

        self._aggregate(summary)
        return summary

    def _aggregate(self, summary: WalkForwardSummary) -> None:
        """Compute aggregate OOS metrics and detect performance decay."""
        folds = summary.folds
        if not folds:
            return

        pnls = [f.oos_total_pnl for f in folds]
        sharpes = [f.oos_sharpe for f in folds if f.oos_sharpe is not None]
        drawdowns = [f.oos_max_drawdown for f in folds if f.oos_max_drawdown is not None]
        win_rates = [f.oos_win_rate for f in folds if f.oos_win_rate is not None]
        pfs = [f.oos_profit_factor for f in folds if f.oos_profit_factor is not None]

        summary.total_oos_pnl = sum(pnls)
        summary.avg_oos_sharpe = sum(sharpes) / len(sharpes) if sharpes else None
        summary.avg_oos_drawdown = sum(drawdowns) / len(drawdowns) if drawdowns else None
        summary.avg_oos_win_rate = sum(win_rates) / len(win_rates) if win_rates else None
        summary.avg_oos_profit_factor = sum(pfs) / len(pfs) if pfs else None

        # Decay detection: linear regression of OOS PnL across folds
        if len(pnls) >= 3:
            n = len(pnls)
            xs = list(range(n))
            x_mean = sum(xs) / n
            y_mean = sum(pnls) / n
            ss_xy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, pnls))
            ss_xx = sum((x - x_mean) ** 2 for x in xs)
            if ss_xx > 0:
                slope = ss_xy / ss_xx
                summary.decay_slope = slope
                # R² for context
                y_pred = [x_mean + slope * (x - x_mean) + y_mean - slope * x_mean for x in xs]
                ss_res = sum((y - yp) ** 2 for y, yp in zip(pnls, y_pred))
                ss_tot = sum((y - y_mean) ** 2 for y in pnls)
                summary.decay_r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
                # Decay = consistently negative slope
                summary.is_decay_detected = slope < 0 and summary.decay_r_squared > 0.4

        logger.info(
            f"WalkForward {summary.account_name}/{summary.symbol}: "
            f"{summary.n_folds} folds | Total OOS PnL={summary.total_oos_pnl:.0f} | "
            f"Decay={'YES' if summary.is_decay_detected else 'NO'}"
        )
