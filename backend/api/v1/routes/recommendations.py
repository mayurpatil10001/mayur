"""
backend/api/v1/routes/recommendations.py
==========================================
GET /api/v1/recommendations              — top promoted time slots with full metrics
GET /api/v1/recommendations/{account}    — account-specific recommendations
POST /api/v1/recommendations/refresh     — recompute recommendations (async)
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from sqlalchemy import select

from backend.api.dependencies import AuthRequired, DBSession
from backend.models.trade import Trade
from backend.schemas.analytics import TimeBinMetricsSchema
from backend.schemas.walkforward import JobStatusSchema
from backend.services.analytics.time_bin_analyzer import TimeBinAnalyzer, TradeSummary
from backend.core.config import settings

router = APIRouter()


class RecommendationSchema(TimeBinMetricsSchema):
    """Extended time-bin metrics with recommendation context."""
    rank: int = 0
    recommendation: str = ""   # "STRONG BUY" | "BUY" | "WATCH" | "AVOID"
    confidence: str = ""       # "HIGH" | "MEDIUM" | "LOW"


def _classify(metrics) -> tuple[str, str]:
    """Generate recommendation label and confidence tier."""
    if not metrics.is_promoted:
        return "AVOID", "LOW"

    expectancy = metrics.expectancy or 0.0
    sharpe = metrics.sharpe_ratio or 0.0
    pf = metrics.profit_factor or 0.0
    wr = metrics.win_rate or 0.0

    if expectancy > 50 and sharpe > 1.0 and pf > 1.5 and wr > 0.55:
        return "STRONG BUY", "HIGH"
    elif expectancy > 20 and sharpe > 0.5 and pf > 1.2:
        return "BUY", "MEDIUM"
    elif metrics.bh_fdr_pvalue is not None and metrics.bh_fdr_pvalue < settings.BH_FDR_ALPHA:
        return "WATCH", "LOW"
    else:
        return "AVOID", "LOW"


async def _get_recommendations(
    db: DBSession,
    account: str | None = None,
    symbol: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort_by: str = "sharpe_ratio",
    top_n: int = 20,
) -> list[RecommendationSchema]:
    stmt = (
        select(
            Trade.account_name, Trade.symbol, Trade.time_slot_ny,
            Trade.realized_pnl, Trade.entry_time,
        )
        .where(Trade.is_ghost == False)
        .where(Trade.time_slot_ny.isnot(None))
    )
    if account:
        stmt = stmt.where(Trade.account_name == account)
    if symbol:
        stmt = stmt.where(Trade.symbol == symbol)
    if date_from:
        stmt = stmt.where(Trade.session_date >= date_from)
    if date_to:
        stmt = stmt.where(Trade.session_date <= date_to)

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
    )
    grid = analyzer.analyze(trade_summaries)
    promoted = analyzer.get_promoted_slots(grid, top_n=top_n, sort_by=sort_by)

    recommendations = []
    for rank, m in enumerate(promoted, start=1):
        rec_label, confidence = _classify(m)
        recommendations.append(
            RecommendationSchema(
                rank=rank,
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
                recommendation=rec_label,
                confidence=confidence,
            )
        )
    return recommendations


@router.get(
    "",
    response_model=list[RecommendationSchema],
    summary="Top promoted time slots ranked by Sharpe (all accounts)",
)
async def get_recommendations(
    _auth: AuthRequired,
    db: DBSession,
    account: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    sort_by: str = Query(default="sharpe_ratio", enum=["sharpe_ratio", "expectancy", "sortino_ratio", "total_pnl"]),
    top_n: int = Query(default=20, ge=1, le=100),
) -> list[RecommendationSchema]:
    return await _get_recommendations(
        db=db, account=account, symbol=symbol,
        date_from=date_from, date_to=date_to,
        sort_by=sort_by, top_n=top_n,
    )


@router.get(
    "/{account}",
    response_model=list[RecommendationSchema],
    summary="Recommendations for a specific account",
)
async def get_recommendations_for_account(
    account: str,
    _auth: AuthRequired,
    db: DBSession,
    symbol: str | None = Query(default=None),
    sort_by: str = Query(default="sharpe_ratio", enum=["sharpe_ratio", "expectancy", "sortino_ratio"]),
    top_n: int = Query(default=10, ge=1, le=50),
) -> list[RecommendationSchema]:
    return await _get_recommendations(
        db=db, account=account, symbol=symbol, sort_by=sort_by, top_n=top_n,
    )


@router.post(
    "/refresh",
    response_model=JobStatusSchema,
    summary="Recompute BH-FDR recommendations (marks existing promoted trades, async)",
)
async def refresh_recommendations(
    _auth: AuthRequired,
    db: DBSession,
    account: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
) -> JobStatusSchema:
    """
    Recompute which trades are in promoted slots and update Trade.is_promoted.
    Runs synchronously (fast enough for < 50K trades).
    """
    recs = await _get_recommendations(db=db, account=account, symbol=symbol, top_n=500)
    promoted_keys = {(r.account_name, r.symbol, r.time_slot_ny) for r in recs}

    from sqlalchemy import update
    # Reset all promoted flags for this account/symbol scope
    reset_stmt = update(Trade).where(Trade.is_ghost == False)
    if account:
        reset_stmt = reset_stmt.where(Trade.account_name == account)
    if symbol:
        reset_stmt = reset_stmt.where(Trade.symbol == symbol)
    reset_stmt = reset_stmt.values(is_promoted=False)
    await db.execute(reset_stmt)

    # Re-promote matching trades
    for acc, sym, slot in promoted_keys:
        promote_stmt = (
            update(Trade)
            .where(Trade.account_name == acc)
            .where(Trade.symbol == sym)
            .where(Trade.time_slot_ny == slot)
            .values(is_promoted=True)
        )
        await db.execute(promote_stmt)

    await db.commit()

    return JobStatusSchema(
        job_id="inline",
        status="COMPLETE",
        message=f"Refreshed {len(promoted_keys)} promoted slots. "
                f"Updated trade flags for account={account or 'all'}, symbol={symbol or 'all'}.",
    )
