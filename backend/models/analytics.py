"""
backend/models/analytics.py
============================
ORM models for analytics results: TimeBinResult, WalkForwardResult, MonteCarloResult.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class TimeBinResult(Base):
    """
    BH-FDR analyzed performance result for a specific (account, symbol, time_slot_ny).
    Promoted slots (is_promoted=True) are used for recommendations.
    """

    __tablename__ = "time_bin_results"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    time_slot_ny: Mapped[str] = mapped_column(
        String(5), nullable=False, comment="HH:MM New York time (30-min bucket)"
    )

    # Trade statistics
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    expectancy: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Expected value per trade = win_rate*avg_win - loss_rate*avg_loss"
    )

    # Risk-adjusted metrics
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Statistical testing
    wilcoxon_pvalue: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Wilcoxon signed-rank p-value (PnL vs 0)"
    )
    bh_fdr_pvalue: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="BH-FDR corrected p-value"
    )
    is_promoted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if bh_fdr_pvalue < alpha AND trade_count >= min_trades",
    )

    # Metadata
    analysis_date: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="Date this analysis was computed YYYY-MM-DD"
    )
    data_from: Mapped[str | None] = mapped_column(String(10), nullable=True)
    data_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_tbr_acc_sym_slot", "account_name", "symbol", "time_slot_ny"),
        Index("idx_tbr_promoted", "is_promoted", "sharpe_ratio"),
    )


class WalkForwardResult(Base):
    """
    Aggregated walk-forward test result for one (account, symbol) pair.
    """

    __tablename__ = "walk_forward_results"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    # Walk-forward configuration
    n_folds: Mapped[int] = mapped_column(Integer, nullable=False)
    in_sample_days: Mapped[int] = mapped_column(Integer, nullable=False)
    out_of_sample_days: Mapped[int] = mapped_column(Integer, nullable=False)

    # Aggregated OOS results
    oos_total_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    oos_win_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    oos_sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)
    oos_max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    oos_profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Performance decay
    is_decay_detected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    decay_slope: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Linear regression slope of OOS PnL across folds"
    )

    # Detailed per-fold results stored as JSON
    fold_details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="List of per-fold metrics: {fold, is_start, oos_start, oos_pnl, oos_sharpe, ...}",
    )

    run_date: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MonteCarloResult(Base):
    """Monte Carlo simulation result for an (account, symbol) pair."""

    __tablename__ = "monte_carlo_results"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    # Simulation config
    n_simulations: Mapped[int] = mapped_column(Integer, nullable=False)
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False)
    ruin_threshold: Mapped[float] = mapped_column(Float, nullable=False)

    # Percentile equity curves (JSON arrays)
    p05_curve: Mapped[list | None] = mapped_column(JSON, nullable=True)
    p50_curve: Mapped[list | None] = mapped_column(JSON, nullable=True)
    p95_curve: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Summary statistics
    median_final_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    p05_final_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_final_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    median_max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    ruin_probability: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="Fraction of simulations that hit ruin_threshold drawdown"
    )
    max_drawdown_histogram: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="[{bin_start, bin_end, count}, ...]"
    )

    run_date: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ImportJob(Base):
    """Tracks the status of a binary log import job."""

    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="PENDING",
        comment="PENDING | RUNNING | COMPLETE | FAILED",
    )
    data_dir: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_filter: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Comma-separated account names, or NULL for all"
    )

    # Progress
    files_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fills_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ghosts_dropped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    trades_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
