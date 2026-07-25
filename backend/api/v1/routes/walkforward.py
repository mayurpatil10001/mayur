"""
backend/api/v1/routes/walkforward.py
=====================================
POST /api/v1/walkforward/run           — trigger WF test (background task)
GET  /api/v1/walkforward/jobs/{job_id} — poll job status
GET  /api/v1/walkforward/results/{job_id} — retrieve completed results
GET  /api/v1/walkforward/latest        — most recent WF result for account/symbol
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy import select

from backend.api.dependencies import AuthRequired, DBSession
from backend.models.analytics import ImportJob, WalkForwardResult
from backend.schemas.walkforward import (
    FoldResultSchema,
    JobStatusSchema,
    WalkForwardResultSchema,
    WalkForwardRunRequest,
)

router = APIRouter()


async def _run_walk_forward_job(job_id: str, request: WalkForwardRunRequest) -> None:
    """Background task: run walk-forward engine and persist results."""
    from backend.db.session import get_db_context
    from backend.services.walkforward.walk_forward_engine import TradeRecord, WalkForwardEngine
    from backend.models.trade import Trade
    from sqlalchemy import select

    async with get_db_context() as db:
        # Mark job as RUNNING
        job_result = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
        job = job_result.scalar_one_or_none()
        if not job:
            return
        job.status = "RUNNING"
        job.started_at = datetime.now(timezone.utc)
        await db.commit()

        try:
            # Fetch trades
            stmt = (
                select(
                    Trade.account_name, Trade.symbol, Trade.session_date,
                    Trade.time_slot_ny, Trade.realized_pnl, Trade.entry_time,
                )
                .where(Trade.account_name == request.account)
                .where(Trade.symbol == request.symbol)
                .where(Trade.is_ghost == False)
                .where(Trade.time_slot_ny.isnot(None))
            )
            result = await db.execute(stmt)
            rows = result.all()

            trades = [
                TradeRecord(
                    account_name=r.account_name,
                    symbol=r.symbol,
                    session_date=r.session_date,
                    time_slot_ny=r.time_slot_ny or "00:00",
                    realized_pnl=r.realized_pnl,
                    entry_time=r.entry_time,
                )
                for r in rows
                if r.time_slot_ny
            ]

            engine = WalkForwardEngine(
                in_sample_days=request.in_sample_days,
                out_of_sample_days=request.out_of_sample_days,
                bh_alpha=request.bh_alpha,
                min_trades_per_slot=request.min_trades_per_slot,
            )
            summary = engine.run(trades, account=request.account, symbol=request.symbol)

            # Persist result
            wf_result = WalkForwardResult(
                id=job_id,
                account_name=summary.account_name,
                symbol=summary.symbol,
                n_folds=summary.n_folds,
                in_sample_days=summary.in_sample_days,
                out_of_sample_days=summary.out_of_sample_days,
                oos_total_pnl=summary.total_oos_pnl,
                oos_win_rate=summary.avg_oos_win_rate,
                oos_sharpe=summary.avg_oos_sharpe,
                oos_max_drawdown=summary.avg_oos_drawdown,
                oos_profit_factor=summary.avg_oos_profit_factor,
                is_decay_detected=summary.is_decay_detected,
                decay_slope=summary.decay_slope,
                fold_details=[
                    {
                        "fold_index": f.fold_index,
                        "is_start": f.is_start, "is_end": f.is_end,
                        "oos_start": f.oos_start, "oos_end": f.oos_end,
                        "is_trade_count": f.is_trade_count,
                        "is_promoted_slots": f.is_promoted_slots,
                        "oos_trade_count": f.oos_trade_count,
                        "oos_total_pnl": f.oos_total_pnl,
                        "oos_win_rate": f.oos_win_rate,
                        "oos_sharpe": f.oos_sharpe,
                        "oos_max_drawdown": f.oos_max_drawdown,
                        "oos_profit_factor": f.oos_profit_factor,
                        "oos_expectancy": f.oos_expectancy,
                    }
                    for f in summary.folds
                ],
                run_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            )
            db.add(wf_result)

            # Update job
            job.status = "COMPLETE"
            job.completed_at = datetime.now(timezone.utc)
            if job.started_at:
                job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            await db.commit()

        except Exception as e:
            job.status = "FAILED"
            job.error_detail = str(e)
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise


@router.post(
    "/run",
    response_model=JobStatusSchema,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger walk-forward test (async background job)",
)
async def run_walk_forward(
    request: WalkForwardRunRequest,
    background_tasks: BackgroundTasks,
    _auth: AuthRequired,
    db: DBSession,
) -> JobStatusSchema:
    job_id = str(uuid.uuid4())
    job = ImportJob(
        id=job_id,
        status="PENDING",
        data_dir=f"{request.account}/{request.symbol}",
        account_filter=request.account,
    )
    db.add(job)
    await db.commit()

    background_tasks.add_task(_run_walk_forward_job, job_id, request)

    return JobStatusSchema(
        job_id=job_id,
        status="PENDING",
        message=f"Walk-forward job queued for {request.account}/{request.symbol}",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusSchema,
    summary="Poll walk-forward job status",
)
async def get_job_status(
    job_id: str,
    _auth: AuthRequired,
    db: DBSession,
) -> JobStatusSchema:
    result = await db.execute(select(ImportJob).where(ImportJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return JobStatusSchema(
        job_id=job.id,
        status=job.status,
        message=job.error_detail,
    )


@router.get(
    "/results/{job_id}",
    response_model=WalkForwardResultSchema,
    summary="Retrieve completed walk-forward results",
)
async def get_results(
    job_id: str,
    _auth: AuthRequired,
    db: DBSession,
) -> WalkForwardResultSchema:
    result = await db.execute(select(WalkForwardResult).where(WalkForwardResult.id == job_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Walk-forward result {job_id} not found")

    folds = [FoldResultSchema(**f) for f in (wf.fold_details or [])]
    return WalkForwardResultSchema(
        account_name=wf.account_name,
        symbol=wf.symbol,
        n_folds=wf.n_folds,
        in_sample_days=wf.in_sample_days,
        out_of_sample_days=wf.out_of_sample_days,
        total_oos_pnl=wf.oos_total_pnl or 0.0,
        avg_oos_sharpe=wf.oos_sharpe,
        avg_oos_drawdown=wf.oos_max_drawdown,
        avg_oos_win_rate=wf.oos_win_rate,
        avg_oos_profit_factor=wf.oos_profit_factor,
        is_decay_detected=wf.is_decay_detected,
        decay_slope=wf.decay_slope,
        decay_r_squared=None,
        folds=folds,
    )


@router.get(
    "/latest",
    response_model=WalkForwardResultSchema,
    summary="Most recent walk-forward result for account/symbol",
)
async def latest_result(
    _auth: AuthRequired,
    db: DBSession,
    account: str = Query(...),
    symbol: str = Query(...),
) -> WalkForwardResultSchema:
    result = await db.execute(
        select(WalkForwardResult)
        .where(WalkForwardResult.account_name == account)
        .where(WalkForwardResult.symbol == symbol)
        .order_by(WalkForwardResult.created_at.desc())
        .limit(1)
    )
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail=f"No walk-forward results for {account}/{symbol}")

    folds = [FoldResultSchema(**f) for f in (wf.fold_details or [])]
    return WalkForwardResultSchema(
        account_name=wf.account_name,
        symbol=wf.symbol,
        n_folds=wf.n_folds,
        in_sample_days=wf.in_sample_days,
        out_of_sample_days=wf.out_of_sample_days,
        total_oos_pnl=wf.oos_total_pnl or 0.0,
        avg_oos_sharpe=wf.oos_sharpe,
        avg_oos_drawdown=wf.oos_max_drawdown,
        avg_oos_win_rate=wf.oos_win_rate,
        avg_oos_profit_factor=wf.oos_profit_factor,
        is_decay_detected=wf.is_decay_detected,
        decay_slope=wf.decay_slope,
        decay_r_squared=None,
        folds=folds,
    )
