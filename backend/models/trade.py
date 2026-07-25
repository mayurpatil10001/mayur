"""
backend/models/trade.py
=======================
SQLAlchemy ORM models for trade data.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
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


class Trade(Base):
    """
    A completed round-trip trade (entry + exit pair).
    Produced by the GFRE FIFO pairing pipeline from clean binary log fills.
    """

    __tablename__ = "processed_trades"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # Account / symbol identity
    account_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    strategy_tag: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="AutoTrader_ note from Tag 0x82. NULL on ghost fills.",
    )

    # Timing
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    session_date: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        index=True,
        comment="UTC session date YYYY-MM-DD. Used for daily grouping.",
    )
    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Position
    side: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
        comment="BUY or SELL",
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Prices
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)

    # PnL
    realized_pnl: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Realized PnL in USD (or instrument currency).",
    )
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_pnl: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="realized_pnl - commission",
    )

    # Time-slot analysis (New York timezone)
    time_slot_ny: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        index=True,
        comment="HH:MM New York time slot (30-min bucket). e.g. '09:30'",
    )
    hour_ny: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minute_of_hour_ny: Mapped[int | None] = mapped_column(Integer, nullable=True)
    day_of_week: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="0=Monday, 6=Sunday"
    )

    # Quality flags
    is_ghost: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if this fill was flagged as a ghost fill (no strategy tag).",
    )
    is_promoted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if the time_slot_ny has passed BH-FDR promotion gate.",
    )
    is_outlier: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True if this trade was flagged as a statistical outlier.",
    )

    # Metadata
    import_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # ── Composite indexes for common query patterns ────────────────────────────
    __table_args__ = (
        # Most common: account + symbol + date range
        Index("idx_trade_acc_sym_entry", "account_name", "symbol", "entry_time"),
        # Time-bin analysis
        Index("idx_trade_slot_acc", "time_slot_ny", "account_name"),
        # Promoted slots leaderboard
        Index("idx_trade_promoted_acc", "is_promoted", "account_name", "realized_pnl"),
        # Daily aggregation
        Index("idx_trade_session_acc", "session_date", "account_name"),
    )

    def __repr__(self) -> str:
        return (
            f"<Trade {self.id[:8]} | {self.account_name} {self.symbol} "
            f"{self.side} {self.quantity} | PnL={self.realized_pnl:.2f}>"
        )


class PendingFill(Base):
    """
    Unpaired entry fill carried across session boundaries.
    Cleared on next session's FIFO pairing pass.
    """

    __tablename__ = "pending_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_name: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(4), nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_tag: Mapped[str | None] = mapped_column(String(128), nullable=True)
    internal_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_date: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_pending_acc_sym", "account_name", "symbol"),
    )
