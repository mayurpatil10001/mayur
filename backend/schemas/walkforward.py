"""
backend/schemas/walkforward.py
================================
Pydantic schemas for walk-forward and Monte Carlo endpoints.
"""

from __future__ import annotations
from pydantic import BaseModel, Field


class WalkForwardRunRequest(BaseModel):
    account: str = Field(..., description="Account name to analyze")
    symbol: str = Field(..., description="Symbol to analyze (e.g. FDAXM26)")
    in_sample_days: int = Field(default=252, ge=30)
    out_of_sample_days: int = Field(default=63, ge=10)
    bh_alpha: float = Field(default=0.05, ge=0.001, le=0.2)
    min_trades_per_slot: int = Field(default=30, ge=5)


class FoldResultSchema(BaseModel):
    fold_index: int
    is_start: str
    is_end: str
    oos_start: str
    oos_end: str
    is_trade_count: int
    is_promoted_slots: list[str]
    oos_trade_count: int
    oos_total_pnl: float
    oos_win_rate: float | None
    oos_sharpe: float | None
    oos_max_drawdown: float | None
    oos_profit_factor: float | None
    oos_expectancy: float | None


class WalkForwardResultSchema(BaseModel):
    account_name: str
    symbol: str
    n_folds: int
    in_sample_days: int
    out_of_sample_days: int
    total_oos_pnl: float
    avg_oos_sharpe: float | None
    avg_oos_drawdown: float | None
    avg_oos_win_rate: float | None
    avg_oos_profit_factor: float | None
    is_decay_detected: bool
    decay_slope: float | None
    decay_r_squared: float | None
    folds: list[FoldResultSchema]


class MonteCarloRunRequest(BaseModel):
    account: str
    symbol: str
    n_simulations: int = Field(default=10_000, ge=1_000, le=100_000)
    horizon_days: int = Field(default=252, ge=20)
    ruin_threshold: float = Field(default=0.50, ge=0.1, le=1.0)
    promoted_slots_only: bool = True


class MonteCarloResultSchema(BaseModel):
    account_name: str
    symbol: str
    n_simulations: int
    horizon_days: int
    ruin_threshold: float
    p05_curve: list[float]
    p50_curve: list[float]
    p95_curve: list[float]
    median_final_pnl: float | None
    p05_final_pnl: float | None
    p95_final_pnl: float | None
    mean_final_pnl: float | None
    std_final_pnl: float | None
    positive_outcome_probability: float | None
    median_max_drawdown: float | None
    p95_max_drawdown: float | None
    ruin_probability: float | None
    max_drawdown_histogram: list[dict]


class JobStatusSchema(BaseModel):
    job_id: str
    status: str          # PENDING | RUNNING | COMPLETE | FAILED
    progress_pct: float | None = None
    message: str | None = None
