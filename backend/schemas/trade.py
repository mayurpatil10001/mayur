"""
backend/schemas/trade.py
========================
Pydantic response/request schemas for trade data.
No ORM objects cross the API boundary — only these schemas.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class TradeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    account_name: str
    symbol: str
    strategy_tag: str | None = None
    entry_time: datetime
    exit_time: datetime
    session_date: str
    duration_minutes: float | None = None
    side: str
    quantity: int
    entry_price: float
    exit_price: float
    realized_pnl: float
    commission: float
    net_pnl: float | None = None
    time_slot_ny: str | None = None
    hour_ny: int | None = None
    day_of_week: int | None = None
    is_ghost: bool
    is_promoted: bool
    is_outlier: bool
    import_job_id: str | None = None
    created_at: datetime


class TradeSummarySchema(BaseModel):
    """Aggregate summary for a date or date range."""
    session_date: str
    account_name: str
    symbol: str | None = None
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float | None = None
    total_pnl: float
    avg_pnl: float | None = None
    max_drawdown: float | None = None


class PageSchema(BaseModel, Generic[T]):
    """Generic paginated response envelope."""
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "PageSchema[T]":
        import math
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if page_size else 1,
        )
