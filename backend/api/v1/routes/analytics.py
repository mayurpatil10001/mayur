"""
backend/api/v1/routes/analytics.py
=====================================
GET /api/v1/analytics/summary       — overall performance snapshot
GET /api/v1/analytics/by-account    — per-account leaderboard (Sortino ranked)
GET /api/v1/analytics/by-symbol     — per-symbol breakdown
GET /api/v1/analytics/time-slots    — BH-FDR time-bin grid + heatmap
GET /api/v1/analytics/pnl-curve     — daily cumulative PnL curve
GET /api/v1/analytics/drawdown      — drawdown series
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from backend.api.dependencies import AuthRequired, DBSession, TradeFiltersDep
from backend.models.trade import Trade
from backend.schemas.analytics import (
    AccountRankingSchema,
    DrawdownPoint,
    HeatmapSchema,
    PerformanceSnapshotSchema,
    PnLCurvePoint,
    SymbolBreakdownSchema,
    TimeBinGridSchema,
    TimeBinMetricsSchema,
)
from backend.services.analytics.performance_calculator import full_performance_snapshot
from backend.services.analytics.time_bin_analyzer import (
    TimeBinAnalyzer,
    TradeSummary,
)
from backend.core.config import settings

router = APIRouter()


async def _fetch_pnls(db: DBSession, filters: TradeFiltersDep) -> list[float]:
    """Fetch all non-ghost trade PnLs matching filters."""
    stmt = select(Trade.realized_pnl).where(Trade.is_ghost == False)
    if filters.account:
        stmt = stmt.where(Trade.account_name == filters.account)
    if filters.symbol:
        stmt = stmt.where(Trade.symbol == filters.symbol)
    if filters.date_from:
        stmt = stmt.where(Trade.session_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Trade.session_date <= filters.date_to)
    if filters.is_promoted is not None:
        stmt = stmt.where(Trade.is_promoted == filters.is_promoted)
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


@router.get(
    "/summary",
    response_model=PerformanceSnapshotSchema,
    summary="Full performance snapshot for the given filters",
)
async def analytics_summary(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
) -> PerformanceSnapshotSchema:
    pnls = await _fetch_pnls(db, filters)
    snap = full_performance_snapshot(pnls)
    return PerformanceSnapshotSchema(
        account_name=filters.account,
        symbol=filters.symbol,
        date_from=filters.date_from,
        date_to=filters.date_to,
        **snap,
    )


@router.get(
    "/by-account",
    response_model=list[AccountRankingSchema],
    summary="Sortino-ranked account leaderboard",
)
async def by_account(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
    sort_by: str = Query(default="sortino_ratio", enum=["sortino_ratio", "sharpe_ratio", "net_pnl", "win_rate"]),
    top_n: int = Query(default=20, ge=1, le=100),
) -> list[AccountRankingSchema]:
    # Fetch trades grouped by account
    stmt = (
        select(Trade.account_name, Trade.symbol, Trade.realized_pnl, Trade.is_promoted)
        .where(Trade.is_ghost == False)
    )
    if filters.date_from:
        stmt = stmt.where(Trade.session_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Trade.session_date <= filters.date_to)
    if filters.symbol:
        stmt = stmt.where(Trade.symbol == filters.symbol)

    result = await db.execute(stmt)
    rows = result.all()

    # Group by account
    groups: dict[tuple, list[float]] = defaultdict(list)
    promoted_counts: dict[tuple, int] = defaultdict(int)
    for row in rows:
        key = (row.account_name, row.symbol)
        groups[key].append(row.realized_pnl)
        if row.is_promoted:
            promoted_counts[key] += 1

    rankings = []
    for key, pnls in groups.items():
        account, symbol = key
        snap = full_performance_snapshot(pnls)
        rankings.append(
            AccountRankingSchema(
                rank=0,
                account_name=account,
                symbol=symbol,
                trade_count=snap["trade_count"],
                net_pnl=snap["net_pnl"],
                win_rate=snap["win_rate"],
                sharpe_ratio=snap["sharpe_ratio"],
                sortino_ratio=snap["sortino_ratio"],
                max_drawdown=snap["max_drawdown"],
                promoted_slots=promoted_counts.get(key, 0),
            )
        )

    # Sort and rank
    sort_key = sort_by
    rankings.sort(key=lambda r: getattr(r, sort_key) or 0.0, reverse=True)
    for i, r in enumerate(rankings[:top_n], start=1):
        r.rank = i

    return rankings[:top_n]


@router.get(
    "/by-symbol",
    response_model=list[SymbolBreakdownSchema],
    summary="Per-symbol performance breakdown",
)
async def by_symbol(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
) -> list[SymbolBreakdownSchema]:
    stmt = (
        select(Trade.symbol, Trade.account_name, Trade.realized_pnl, Trade.is_promoted)
        .where(Trade.is_ghost == False)
    )
    if filters.account:
        stmt = stmt.where(Trade.account_name == filters.account)
    if filters.date_from:
        stmt = stmt.where(Trade.session_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Trade.session_date <= filters.date_to)

    result = await db.execute(stmt)
    rows = result.all()

    groups: dict[tuple, list[float]] = defaultdict(list)
    promoted_counts: dict[tuple, int] = defaultdict(int)
    for row in rows:
        key = (row.symbol, row.account_name)
        groups[key].append(row.realized_pnl)
        if row.is_promoted:
            promoted_counts[key] += 1

    breakdowns = []
    for (symbol, account), pnls in groups.items():
        snap = full_performance_snapshot(pnls)
        breakdowns.append(
            SymbolBreakdownSchema(
                symbol=symbol,
                account_name=account,
                trade_count=snap["trade_count"],
                net_pnl=snap["net_pnl"],
                win_rate=snap["win_rate"],
                sharpe_ratio=snap["sharpe_ratio"],
                promoted_slots=promoted_counts.get((symbol, account), 0),
            )
        )

    breakdowns.sort(key=lambda b: b.net_pnl, reverse=True)
    return breakdowns


@router.get(
    "/time-slots",
    response_model=TimeBinGridSchema,
    summary="BH-FDR analyzed time-slot grid with optional heatmap",
)
async def time_slots(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
    include_heatmap: bool = Query(default=True),
    resolution_minutes: int = Query(default=30, enum=[15, 30, 60]),
) -> TimeBinGridSchema:
    stmt = (
        select(
            Trade.account_name, Trade.symbol, Trade.time_slot_ny,
            Trade.realized_pnl, Trade.entry_time,
        )
        .where(Trade.is_ghost == False)
        .where(Trade.time_slot_ny.isnot(None))
    )
    if filters.account:
        stmt = stmt.where(Trade.account_name == filters.account)
    if filters.symbol:
        stmt = stmt.where(Trade.symbol == filters.symbol)
    if filters.date_from:
        stmt = stmt.where(Trade.session_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Trade.session_date <= filters.date_to)

    result = await db.execute(stmt)
    rows = result.all()

    trade_summaries = [
        TradeSummary(
            account_name=r.account_name,
            symbol=r.symbol,
            time_slot_ny=r.time_slot_ny,
            realized_pnl=r.realized_pnl,
            entry_time=r.entry_time,
        )
        for r in rows
    ]

    analyzer = TimeBinAnalyzer(
        alpha=settings.BH_FDR_ALPHA,
        min_trades=settings.MIN_TRADES_FOR_PROMOTION,
        slot_resolution_minutes=resolution_minutes,
    )
    grid = analyzer.analyze(trade_summaries)

    promoted = sum(1 for m in grid.values() if m.is_promoted)
    slot_schemas = [
        TimeBinMetricsSchema(
            account_name=m.account_name,
            symbol=m.symbol,
            time_slot_ny=m.time_slot_ny,
            trade_count=m.trade_count,
            win_count=m.win_count,
            loss_count=m.loss_count,
            win_rate=m.win_rate,
            total_pnl=m.total_pnl,
            avg_pnl=m.avg_pnl,
            expectancy=m.expectancy,
            profit_factor=m.profit_factor,
            sharpe_ratio=m.sharpe_ratio,
            sortino_ratio=m.sortino_ratio,
            max_drawdown=m.max_drawdown,
            wilcoxon_pvalue=m.wilcoxon_pvalue,
            bh_fdr_pvalue=m.bh_fdr_pvalue,
            is_promoted=m.is_promoted,
        )
        for m in sorted(grid.values(), key=lambda m: m.total_pnl, reverse=True)
    ]

    heatmap_data = None
    if include_heatmap:
        raw = analyzer.to_heatmap_matrix(grid, metric="total_pnl")
        heatmap_data = raw

    return TimeBinGridSchema(
        resolution=f"{resolution_minutes}min",
        timezone="America/New_York",
        alpha=settings.BH_FDR_ALPHA,
        total_slots=len(grid),
        promoted_slots=promoted,
        slots=slot_schemas,
        heatmap=heatmap_data,
    )


@router.get(
    "/pnl-curve",
    response_model=list[PnLCurvePoint],
    summary="Daily cumulative PnL curve",
)
async def pnl_curve(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
) -> list[PnLCurvePoint]:
    stmt = (
        select(Trade.session_date, func.sum(Trade.realized_pnl).label("daily_pnl"))
        .where(Trade.is_ghost == False)
        .group_by(Trade.session_date)
        .order_by(Trade.session_date)
    )
    if filters.account:
        stmt = stmt.where(Trade.account_name == filters.account)
    if filters.symbol:
        stmt = stmt.where(Trade.symbol == filters.symbol)
    if filters.date_from:
        stmt = stmt.where(Trade.session_date >= filters.date_from)
    if filters.date_to:
        stmt = stmt.where(Trade.session_date <= filters.date_to)
    if filters.is_promoted is not None:
        stmt = stmt.where(Trade.is_promoted == filters.is_promoted)

    result = await db.execute(stmt)
    rows = result.all()

    points = []
    cumulative = 0.0
    for row in rows:
        daily = row.daily_pnl or 0.0
        cumulative += daily
        points.append(PnLCurvePoint(
            date=row.session_date,
            daily_pnl=round(daily, 2),
            cumulative_pnl=round(cumulative, 2),
        ))
    return points


@router.get(
    "/drawdown",
    response_model=list[DrawdownPoint],
    summary="Daily drawdown from equity peak",
)
async def drawdown_series(
    _auth: AuthRequired,
    db: DBSession,
    filters: TradeFiltersDep,
    initial_equity: float = Query(default=100_000.0, description="Starting capital for % calculation"),
) -> list[DrawdownPoint]:
    curve = await pnl_curve(_auth=_auth, db=db, filters=filters)

    peak = 0.0
    points = []
    for pt in curve:
        equity = initial_equity + pt.cumulative_pnl
        if equity > peak:
            peak = equity
        dd = peak - equity
        dd_pct = dd / peak if peak > 0 else 0.0
        points.append(DrawdownPoint(
            date=pt.date,
            drawdown=round(dd, 2),
            drawdown_pct=round(dd_pct, 6),
        ))
    return points
