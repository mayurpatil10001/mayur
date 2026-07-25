"""
backend/services/analytics/time_bin_analyzer.py
================================================
Time-bin performance analyzer with Benjamini-Hochberg FDR correction.

Pipeline:
  1. Group trades by (account, symbol, time_slot_ny)
  2. Run Wilcoxon signed-rank test per slot (PnL distribution vs 0)
  3. Collect all p-values and apply BH-FDR correction across all slots
  4. Promote slots where: bh_corrected_p < alpha AND trade_count >= min_trades
  5. Return ranked TimeBinGrid sorted by expectancy
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

logger = logging.getLogger(__name__)

try:
    from scipy.stats import wilcoxon
    import numpy as np
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    logger.warning("scipy not installed — BH-FDR analysis disabled. Install: pip install scipy numpy")


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class TradeSummary:
    """Minimal trade data needed for time-bin analysis."""
    account_name: str
    symbol: str
    time_slot_ny: str      # "HH:MM" format
    realized_pnl: float
    entry_time: datetime


@dataclass
class TimeBinMetrics:
    """Performance metrics for a single (account, symbol, time_slot_ny) combination."""
    account_name: str
    symbol: str
    time_slot_ny: str
    trade_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float | None = None
    total_pnl: float = 0.0
    avg_pnl: float | None = None
    expectancy: float | None = None
    profit_factor: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float | None = None
    wilcoxon_pvalue: float | None = None
    bh_fdr_pvalue: float | None = None
    is_promoted: bool = False
    pnls: list[float] = field(default_factory=list, repr=False)


# ── BH-FDR correction ─────────────────────────────────────────────────────────

def benjamini_hochberg(pvalues: list[float], alpha: float = 0.05) -> list[float]:
    """
    Apply Benjamini-Hochberg FDR correction to a list of p-values.

    Returns a list of BH-adjusted p-values in the same order as input.
    Follows the BH(1995) step-up procedure.
    """
    n = len(pvalues)
    if n == 0:
        return []

    # Pair with original index, sort by p-value ascending
    indexed = sorted(enumerate(pvalues), key=lambda x: x[1])
    adjusted = [1.0] * n

    # Step-up: from largest p-value down to smallest
    min_val = 1.0
    for rank, (orig_idx, pval) in enumerate(reversed(indexed)):
        rank_from_end = n - rank  # rank (1-indexed, from largest p to smallest)
        adjusted_p = pval * n / rank_from_end
        min_val = min(min_val, adjusted_p)
        adjusted[orig_idx] = min_val

    return adjusted


# ── Main Analyzer ─────────────────────────────────────────────────────────────

class TimeBinAnalyzer:
    """
    Analyzes trade performance by time slot and applies BH-FDR promotion gate.

    Usage:
        analyzer = TimeBinAnalyzer(alpha=0.05, min_trades=30)
        grid = analyzer.analyze(trades)
        promoted = analyzer.get_promoted_slots(grid)
    """

    def __init__(
        self,
        alpha: float = 0.05,
        min_trades: int = 30,
        slot_resolution_minutes: int = 30,
    ) -> None:
        self.alpha = alpha
        self.min_trades = min_trades
        self.slot_resolution_minutes = slot_resolution_minutes

    def slot_label(self, entry_time: datetime) -> str:
        """
        Convert entry_time (NY timezone) to slot label "HH:MM".
        Buckets into slot_resolution_minutes intervals.
        """
        if entry_time.tzinfo is None:
            entry_time = entry_time.replace(tzinfo=timezone.utc)
        # Convert to New York time
        try:
            from zoneinfo import ZoneInfo
            ny_tz = ZoneInfo("America/New_York")
            ny_time = entry_time.astimezone(ny_tz)
        except Exception:
            ny_time = entry_time  # Fallback: treat as-is

        # Round down to nearest slot
        slot_minute = (ny_time.minute // self.slot_resolution_minutes) * self.slot_resolution_minutes
        return f"{ny_time.hour:02d}:{slot_minute:02d}"

    def analyze(self, trades: Sequence[TradeSummary]) -> dict[str, TimeBinMetrics]:
        """
        Full analysis pipeline:
          1. Group trades by (account, symbol, time_slot_ny)
          2. Compute per-slot metrics
          3. Run Wilcoxon test per slot
          4. Apply BH-FDR across all slots
          5. Set is_promoted flag
          6. Return {slot_key: TimeBinMetrics} dict

        Args:
            trades: Sequence of TradeSummary objects.

        Returns:
            Dict keyed by "{account}|{symbol}|{slot}" → TimeBinMetrics.
        """
        from backend.services.analytics.performance_calculator import (
            expectancy as calc_expectancy,
            max_drawdown as calc_max_drawdown,
            profit_factor as calc_profit_factor,
            sharpe_ratio as calc_sharpe,
            sortino_ratio as calc_sortino,
            win_rate as calc_win_rate,
        )

        # ── Group ──────────────────────────────────────────────────────────────
        groups: dict[str, list[float]] = defaultdict(list)
        group_meta: dict[str, tuple[str, str, str]] = {}

        for trade in trades:
            slot = trade.time_slot_ny or self.slot_label(trade.entry_time)
            key = f"{trade.account_name}|{trade.symbol}|{slot}"
            groups[key].append(trade.realized_pnl)
            group_meta[key] = (trade.account_name, trade.symbol, slot)

        # ── Compute per-slot metrics and Wilcoxon p-values ─────────────────────
        metrics_map: dict[str, TimeBinMetrics] = {}
        pvalue_keys: list[str] = []
        pvalues: list[float] = []

        for key, pnls in groups.items():
            account, symbol, slot = group_meta[key]
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]

            m = TimeBinMetrics(
                account_name=account,
                symbol=symbol,
                time_slot_ny=slot,
                trade_count=len(pnls),
                win_count=len(wins),
                loss_count=len(losses),
                win_rate=calc_win_rate(pnls),
                total_pnl=sum(pnls),
                avg_pnl=sum(pnls) / len(pnls) if pnls else None,
                expectancy=calc_expectancy(pnls),
                profit_factor=calc_profit_factor(pnls),
                sharpe_ratio=calc_sharpe(pnls),
                sortino_ratio=calc_sortino(pnls),
                max_drawdown=calc_max_drawdown(pnls),
                pnls=pnls,
            )

            # Wilcoxon signed-rank test (requires scipy)
            if SCIPY_AVAILABLE and len(pnls) >= 10:
                try:
                    non_zero = [p for p in pnls if p != 0]
                    if len(non_zero) >= 5:
                        _, pval = wilcoxon(non_zero, alternative="greater", zero_method="wilcox")
                        m.wilcoxon_pvalue = float(pval)
                        pvalue_keys.append(key)
                        pvalues.append(float(pval))
                except Exception as e:
                    logger.debug(f"Wilcoxon failed for {key}: {e}")

            metrics_map[key] = m

        # ── BH-FDR correction ─────────────────────────────────────────────────
        if pvalues:
            bh_adjusted = benjamini_hochberg(pvalues, alpha=self.alpha)
            for key, adj_p in zip(pvalue_keys, bh_adjusted):
                m = metrics_map[key]
                m.bh_fdr_pvalue = adj_p
                m.is_promoted = (
                    adj_p < self.alpha
                    and m.trade_count >= self.min_trades
                    and (m.expectancy or 0) > 0
                )

        promoted_count = sum(1 for m in metrics_map.values() if m.is_promoted)
        logger.info(
            f"TimeBinAnalyzer: {len(metrics_map)} slots analyzed | "
            f"{promoted_count} promoted (BH-FDR α={self.alpha}, min_trades={self.min_trades})"
        )

        return metrics_map

    def get_promoted_slots(
        self,
        grid: dict[str, TimeBinMetrics],
        top_n: int | None = None,
        sort_by: str = "expectancy",
    ) -> list[TimeBinMetrics]:
        """
        Return promoted slots sorted by sort_by (default: expectancy).

        Args:
            grid: Output of analyze().
            top_n: Limit results (None = all promoted).
            sort_by: Field to sort by. Options: "expectancy", "sharpe_ratio", "total_pnl".

        Returns:
            Sorted list of promoted TimeBinMetrics.
        """
        promoted = [m for m in grid.values() if m.is_promoted]
        promoted.sort(key=lambda m: getattr(m, sort_by) or 0.0, reverse=True)
        return promoted[:top_n] if top_n else promoted

    def to_heatmap_matrix(
        self,
        grid: dict[str, TimeBinMetrics],
        metric: str = "total_pnl",
    ) -> dict:
        """
        Convert grid to a matrix suitable for Plotly heatmap rendering.

        Returns:
            {
                "accounts": [...],
                "slots": [...],
                "matrix": [[value, ...], ...],   # accounts × slots
                "promoted_mask": [[bool, ...], ...]
            }
        """
        accounts = sorted({m.account_name for m in grid.values()})
        slots = sorted({m.time_slot_ny for m in grid.values()})

        acc_idx = {a: i for i, a in enumerate(accounts)}
        slot_idx = {s: i for i, s in enumerate(slots)}

        matrix = [[None] * len(slots) for _ in range(len(accounts))]
        promoted_mask = [[False] * len(slots) for _ in range(len(accounts))]

        for m in grid.values():
            i = acc_idx[m.account_name]
            j = slot_idx[m.time_slot_ny]
            matrix[i][j] = getattr(m, metric)
            promoted_mask[i][j] = m.is_promoted

        return {
            "accounts": accounts,
            "slots": slots,
            "matrix": matrix,
            "promoted_mask": promoted_mask,
            "metric": metric,
        }
