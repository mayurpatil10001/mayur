"""
backend/api/v1/routes/trades.py
================================
GET /api/v1/trades  — paginated trade list with filters
GET /api/v1/trades/summary — daily PnL summary
GET /api/v1/trades/{trade_id} — single trade
"""

from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from backend.api.dependencies import AuthRequired, DBSession, Pagination, TradeFiltersDep
from backend.models.trade import Trade
from backend.schemas.trade import PageSchema, TradeSummarySchema, TradeSchema

router = APIRouter()


def _apply_filters(stmt, filters):
    """Apply common trade filters to a SQLAlchemy select statement."""
    if filters.account:
        stmt = stmt.where(Trade.account_name == filters.account)
    if filters.symbol:
        stmt = stmt.where(Trade.symbol == filters.symbol)
    if filters.date_from:
        stmt = stmt.where(Trade.session_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Trade.session_date <= filters.date_to)
    if filters.time_slot:
        stmt = stmt.where(Trade.time_slot_ny == filters.time_slot)
    if filters.is_promoted is not None:
        stmt = stmt.where(Trade.is_promoted == filters.is_promoted)
    return stmt


@router.get(
    "",
    response_model=PageSchema[TradeSchema],
    summary="List trades with filters and pagination",
)
async def list_trades(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
    pagination: Pagination,
    sort_by: str = Query(default="entry_time", enum=["entry_time", "session_date", "realized_pnl"]),
    sort_dir: str = Query(default="desc", enum=["asc", "desc"]),
) -> PageSchema[TradeSchema]:
    # Count total
    count_stmt = select(func.count()).select_from(Trade).where(Trade.is_ghost == False)
    count_stmt = _apply_filters(count_stmt, filters)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Fetch page
    sort_col = getattr(Trade, sort_by)
    if sort_dir == "desc":
        sort_col = sort_col.desc()

    stmt = (
        select(Trade)
        .where(Trade.is_ghost == False)
        .order_by(sort_col)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    stmt = _apply_filters(stmt, filters)

    result = await db.execute(stmt)
    trades = result.scalars().all()

    return PageSchema.build(
        items=[TradeSchema.model_validate(t) for t in trades],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get(
    "/summary",
    response_model=list[TradeSummarySchema],
    summary="Daily PnL summary grouped by session_date and account",
)
async def trade_summary(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
) -> list[TradeSummarySchema]:
    stmt = (
        select(
            Trade.session_date,
            Trade.account_name,
            Trade.symbol,
            func.count(Trade.id).label("trade_count"),
            func.sum(Trade.realized_pnl > 0).label("win_count"),
            func.sum(Trade.realized_pnl < 0).label("loss_count"),
            func.sum(Trade.realized_pnl).label("total_pnl"),
            func.avg(Trade.realized_pnl).label("avg_pnl"),
        )
        .where(Trade.is_ghost == False)
        .group_by(Trade.session_date, Trade.account_name, Trade.symbol)
        .order_by(Trade.session_date.desc())
    )
    stmt = _apply_filters(stmt, filters)
    result = await db.execute(stmt)
    rows = result.all()

    summaries = []
    for row in rows:
        win_rate = row.win_count / row.trade_count if row.trade_count else None
        summaries.append(
            TradeSummarySchema(
                session_date=row.session_date,
                account_name=row.account_name,
                symbol=row.symbol,
                trade_count=row.trade_count,
                win_count=row.win_count or 0,
                loss_count=row.loss_count or 0,
                win_rate=win_rate,
                total_pnl=row.total_pnl or 0.0,
                avg_pnl=row.avg_pnl,
            )
        )
    return summaries


@router.get(
    "/{trade_id}",
    response_model=TradeSchema,
    summary="Get a single trade by ID",
)
async def get_trade(
    trade_id: str,
    _auth: AuthRequired,
    db: DBSession,
) -> TradeSchema:
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Trade {trade_id} not found")
    return TradeSchema.model_validate(trade)
