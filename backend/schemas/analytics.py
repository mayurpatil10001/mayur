"""
backend/schemas/analytics.py
=============================
Pydantic schemas for analytics endpoints.
"""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class PerformanceSnapshotSchema(BaseModel):
    """Complete performance metrics for a given filter context."""
    account_name: str | None = None
    symbol: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float | None
    net_pnl: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    expectancy: float | None
    avg_trade_pnl: float | None
    max_drawdown: float
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    largest_win: float | None
    largest_loss: float | None
    max_consecutive_wins: int
    max_consecutive_losses: int


class TimeBinMetricsSchema(BaseModel):
    """Performance metrics for a single time-bin slot."""
    model_config = ConfigDict(from_attributes=True)

    account_name: str
    symbol: str
    time_slot_ny: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float | None
    total_pnl: float
    avg_pnl: float | None
    expectancy: float | None
    profit_factor: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float | None
    wilcoxon_pvalue: float | None
    bh_fdr_pvalue: float | None
    is_promoted: bool


class TimeBinGridSchema(BaseModel):
    """Full time-bin grid with heatmap matrix."""
    resolution: str = "30min"
    timezone: str = "America/New_York"
    alpha: float
    total_slots: int
    promoted_slots: int
    slots: list[TimeBinMetricsSchema]
    heatmap: dict | None = None   # accounts × slots matrix for Plotly


class HeatmapSchema(BaseModel):
    """Plotly-ready heatmap data structure."""
    accounts: list[str]
    slots: list[str]
    matrix: list[list[float | None]]
    promoted_mask: list[list[bool]]
    metric: str


class AccountRankingSchema(BaseModel):
    """Account ranked by a performance metric (Sortino leaderboard)."""
    rank: int
    account_name: str
    symbol: str | None = None
    trade_count: int
    net_pnl: float
    win_rate: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    max_drawdown: float
    promoted_slots: int


class SymbolBreakdownSchema(BaseModel):
    """Per-symbol performance summary."""
    symbol: str
    account_name: str
    trade_count: int
    net_pnl: float
    win_rate: float | None
    sharpe_ratio: float | None
    promoted_slots: int


class PnLCurvePoint(BaseModel):
    date: str
    cumulative_pnl: float
    daily_pnl: float


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float
    drawdown_pct: float
