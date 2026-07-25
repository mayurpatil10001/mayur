"""
backend/services/montecarlo/monte_carlo_engine.py
==================================================
Monte Carlo simulation engine for equity path analysis.

Algorithm:
  - Resample daily trade PnL with replacement (bootstrap)
  - Simulate N=10,000 paths of horizon_days length
  - Compute 5th / 50th / 95th percentile equity curves
  - Compute max drawdown distribution
  - Compute ruin probability (drawdown exceeds ruin_threshold)
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Sequence

logger = logging.getLogger(__name__)

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy not installed — Monte Carlo will use pure Python (slower).")


@dataclass
class MonteCarloConfig:
    n_simulations: int = 10_000
    horizon_days: int = 252        # Trading days to project
    ruin_threshold: float = 0.50   # 50% drawdown = ruin
    confidence_levels: tuple[float, ...] = (0.05, 0.50, 0.95)
    random_seed: int | None = 42


@dataclass
class MonteCarloResult:
    n_simulations: int
    horizon_days: int
    ruin_threshold: float

    # Percentile equity curves (list of floats, length = horizon_days + 1)
    p05_curve: list[float] = field(default_factory=list)
    p50_curve: list[float] = field(default_factory=list)
    p95_curve: list[float] = field(default_factory=list)

    # Terminal PnL distribution
    median_final_pnl: float | None = None
    p05_final_pnl: float | None = None
    p95_final_pnl: float | None = None

    # Drawdown distribution
    median_max_drawdown: float | None = None
    p95_max_drawdown: float | None = None
    ruin_probability: float | None = None  # Fraction of sims hitting ruin_threshold

    # Histogram buckets for max drawdown distribution
    max_drawdown_histogram: list[dict] = field(default_factory=list)

    # Summary stats
    mean_final_pnl: float | None = None
    std_final_pnl: float | None = None
    positive_outcome_probability: float | None = None  # P(final_pnl > 0)


class MonteCarloEngine:
    """
    Bootstrap Monte Carlo simulation for trading equity curves.

    Usage:
        engine = MonteCarloEngine(config)
        result = engine.run(daily_pnls)
    """

    def __init__(self, config: MonteCarloConfig | None = None) -> None:
        self.config = config or MonteCarloConfig()

    def run(self, daily_pnls: Sequence[float]) -> MonteCarloResult:
        """
        Run Monte Carlo simulation.

        Args:
            daily_pnls: Historical daily PnL values (from promoted slots only).
                        Each value represents one trading day's total PnL.

        Returns:
            MonteCarloResult with percentile curves, drawdown distribution,
            and ruin probability.
        """
        cfg = self.config
        pnls = list(daily_pnls)

        if len(pnls) < 10:
            logger.warning(
                f"Monte Carlo: Only {len(pnls)} daily PnL values — need at least 10. "
                "Results will be unreliable."
            )
        if not pnls:
            return MonteCarloResult(
                n_simulations=cfg.n_simulations,
                horizon_days=cfg.horizon_days,
                ruin_threshold=cfg.ruin_threshold,
            )

        logger.info(
            f"Monte Carlo: Running {cfg.n_simulations:,} simulations × "
            f"{cfg.horizon_days} days from {len(pnls)} historical samples..."
        )

        if NUMPY_AVAILABLE:
            return self._run_numpy(pnls)
        else:
            return self._run_pure_python(pnls)

    # ── NumPy implementation (fast) ───────────────────────────────────────────

    def _run_numpy(self, pnls: list[float]) -> MonteCarloResult:
        cfg = self.config
        rng = np.random.default_rng(cfg.random_seed)

        samples = np.array(pnls, dtype=np.float64)

        # Shape: (n_simulations, horizon_days) — random resampling with replacement
        daily_draws = rng.choice(samples, size=(cfg.n_simulations, cfg.horizon_days), replace=True)

        # Cumulative equity paths: shape (n_simulations, horizon_days + 1)
        # Start at 0 (initial equity is relative)
        equity = np.concatenate(
            [np.zeros((cfg.n_simulations, 1)), np.cumsum(daily_draws, axis=1)],
            axis=1,
        )

        # Percentile curves across simulations at each time step
        p05 = np.percentile(equity, 5, axis=0).tolist()
        p50 = np.percentile(equity, 50, axis=0).tolist()
        p95 = np.percentile(equity, 95, axis=0).tolist()

        # Per-simulation max drawdown
        running_max = np.maximum.accumulate(equity, axis=1)
        drawdowns = running_max - equity  # Absolute drawdown per path per day
        max_drawdowns = np.max(drawdowns, axis=1)  # Worst drawdown per sim

        # Ruin: drawdown exceeds ruin_threshold * peak
        # Relative ruin check against running maximum (as proxy for starting capital)
        peak_equity = np.max(np.abs(equity), axis=1)
        # Use a fixed capital base of 100,000 USD for ruin calculation
        CAPITAL_BASE = 100_000.0
        ruin_mask = max_drawdowns > (cfg.ruin_threshold * CAPITAL_BASE)
        ruin_probability = float(np.mean(ruin_mask))

        # Terminal PnL statistics
        final_pnls = equity[:, -1]
        median_final = float(np.median(final_pnls))
        p05_final = float(np.percentile(final_pnls, 5))
        p95_final = float(np.percentile(final_pnls, 95))
        mean_final = float(np.mean(final_pnls))
        std_final = float(np.std(final_pnls))
        pos_prob = float(np.mean(final_pnls > 0))

        # Drawdown statistics
        median_dd = float(np.median(max_drawdowns))
        p95_dd = float(np.percentile(max_drawdowns, 95))

        # Histogram of max drawdowns (20 buckets)
        histogram = self._build_histogram(max_drawdowns.tolist(), n_buckets=20)

        return MonteCarloResult(
            n_simulations=cfg.n_simulations,
            horizon_days=cfg.horizon_days,
            ruin_threshold=cfg.ruin_threshold,
            p05_curve=p05,
            p50_curve=p50,
            p95_curve=p95,
            median_final_pnl=median_final,
            p05_final_pnl=p05_final,
            p95_final_pnl=p95_final,
            mean_final_pnl=mean_final,
            std_final_pnl=std_final,
            positive_outcome_probability=pos_prob,
            median_max_drawdown=median_dd,
            p95_max_drawdown=p95_dd,
            ruin_probability=ruin_probability,
            max_drawdown_histogram=histogram,
        )

    # ── Pure Python fallback (slower) ─────────────────────────────────────────

    def _run_pure_python(self, pnls: list[float]) -> MonteCarloResult:
        cfg = self.config
        if cfg.random_seed is not None:
            random.seed(cfg.random_seed)

        all_paths: list[list[float]] = []
        max_drawdowns: list[float] = []

        for _ in range(cfg.n_simulations):
            # Resample with replacement
            drawn = [random.choice(pnls) for _ in range(cfg.horizon_days)]
            # Compute equity path
            equity = [0.0]
            cum = 0.0
            for d in drawn:
                cum += d
                equity.append(cum)

            all_paths.append(equity)

            # Max drawdown for this path
            peak = 0.0
            max_dd = 0.0
            for v in equity:
                if v > peak:
                    peak = v
                dd = peak - v
                if dd > max_dd:
                    max_dd = dd
            max_drawdowns.append(max_dd)

        # Percentile curves
        n_steps = cfg.horizon_days + 1
        p05 = [_percentile([path[t] for path in all_paths], 5) for t in range(n_steps)]
        p50 = [_percentile([path[t] for path in all_paths], 50) for t in range(n_steps)]
        p95 = [_percentile([path[t] for path in all_paths], 95) for t in range(n_steps)]

        final_pnls = [path[-1] for path in all_paths]
        CAPITAL_BASE = 100_000.0
        ruin_count = sum(1 for dd in max_drawdowns if dd > cfg.ruin_threshold * CAPITAL_BASE)

        histogram = self._build_histogram(max_drawdowns, n_buckets=20)

        return MonteCarloResult(
            n_simulations=cfg.n_simulations,
            horizon_days=cfg.horizon_days,
            ruin_threshold=cfg.ruin_threshold,
            p05_curve=p05,
            p50_curve=p50,
            p95_curve=p95,
            median_final_pnl=_percentile(final_pnls, 50),
            p05_final_pnl=_percentile(final_pnls, 5),
            p95_final_pnl=_percentile(final_pnls, 95),
            mean_final_pnl=sum(final_pnls) / len(final_pnls),
            std_final_pnl=_std(final_pnls),
            positive_outcome_probability=sum(1 for p in final_pnls if p > 0) / len(final_pnls),
            median_max_drawdown=_percentile(max_drawdowns, 50),
            p95_max_drawdown=_percentile(max_drawdowns, 95),
            ruin_probability=ruin_count / cfg.n_simulations,
            max_drawdown_histogram=histogram,
        )

    @staticmethod
    def _build_histogram(values: list[float], n_buckets: int = 20) -> list[dict]:
        if not values:
            return []
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            return [{"bin_start": min_v, "bin_end": max_v, "count": len(values)}]

        bucket_size = (max_v - min_v) / n_buckets
        buckets = [0] * n_buckets
        for v in values:
            idx = min(int((v - min_v) / bucket_size), n_buckets - 1)
            buckets[idx] += 1

        return [
            {
                "bin_start": round(min_v + i * bucket_size, 2),
                "bin_end": round(min_v + (i + 1) * bucket_size, 2),
                "count": buckets[i],
            }
            for i in range(n_buckets)
        ]


# ── Utility functions ─────────────────────────────────────────────────────────

def _percentile(values: list[float], pct: float) -> float:
    """Compute percentile without numpy."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * pct / 100.0
    lo = int(k)
    hi = lo + 1
    if hi >= len(sorted_vals):
        return sorted_vals[lo]
    frac = k - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(var)
