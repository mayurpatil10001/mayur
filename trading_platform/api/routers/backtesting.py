"""
Backtesting API Router — wires up to the existing TimeBinBacktestingEngine.

Provides endpoints for:
  POST /run          — launch a backtest job (async via BackgroundTasks)
  GET  /status/{id}  — poll progress
  GET  /results/{id} — retrieve full results
"""

import uuid
import time
import logging
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# ── In-memory job store (sufficient for single-process server) ──
_jobs: Dict[str, Dict[str, Any]] = {}


# ── Pydantic models ──
class BacktestConfiguration(BaseModel):
    start_date: str
    end_date: str
    initial_capital: float = 100000
    commission_per_trade: float = 1.0
    slippage_bps: float = 1.0
    method: str = "simple_historical"
    training_days: int = 30
    testing_days: int = 7
    rebalance_frequency: str = "daily"
    num_simulations: int = 1000
    confidence_levels: List[float] = [0.95, 0.99]
    num_folds: int = 5
    benchmark_symbol: str = "SPY"
    risk_free_rate: float = 0.02


class TimeBin(BaseModel):
    account_name: str
    hour: int
    minute_bin: int


class StrategyParameters(BaseModel):
    strategy_name: str
    parameters: Dict[str, Any] = {}


class BacktestRequest(BaseModel):
    configuration: BacktestConfiguration
    time_bins: List[TimeBin]
    strategy_parameters: Optional[StrategyParameters] = None
    run_analysis: bool = True
    analysis_types: List[str] = ["PERFORMANCE", "RISK"]


# ── Background worker ──
def _run_backtest_job(job_id: str, request: BacktestRequest):
    """Execute the backtest synchronously in a background thread."""
    job = _jobs[job_id]
    try:
        job["status"] = "RUNNING"
        job["progress"] = 5
        job["message"] = "Connecting to database..."

        db_path = Path("trading_platform.db")
        if not db_path.exists():
            raise FileNotFoundError("Database not found")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Parse symbol from strategy parameters
        symbol = (
            request.strategy_parameters.parameters.get("symbol", "NQ")
            if request.strategy_parameters
            else "NQ"
        )

        job["progress"] = 10
        job["message"] = f"Fetching trades for {symbol}..."

        # Build the WHERE clause for matching time_bins
        bin_conditions = []
        for tb in request.time_bins:
            time_slot = f"{tb.hour:02d}:{tb.minute_bin:02d}"
            bin_conditions.append(
                f"(account_name = '{tb.account_name}' AND "
                f"strftime('%H:%M', entry_time) >= '{time_slot}' AND "
                f"strftime('%H:%M', entry_time) < '{tb.hour:02d}:{tb.minute_bin + 30:02d}')"
            )

        if not bin_conditions:
            raise ValueError("No time bins provided")

        where_bins = " OR ".join(bin_conditions)

        query = f"""
            SELECT entry_time, exit_time, profit_loss, account_name, symbol
            FROM processed_trades
            WHERE symbol LIKE '%{symbol}%'
              AND entry_time >= '{request.configuration.start_date}'
              AND entry_time <= '{request.configuration.end_date}'
              AND ({where_bins})
            ORDER BY entry_time ASC
        """

        cursor.execute(query)
        rows = cursor.fetchall()
        trades = [dict(r) for r in rows]

        job["progress"] = 30
        job["message"] = f"Found {len(trades)} trades. Running backtest..."

        if not trades:
            # No matching trades — produce empty but valid results
            job["results"] = _build_results([], request, symbol)
            job["status"] = "COMPLETED"
            job["progress"] = 100
            job["message"] = "Completed — no matching trades found"
            conn.close()
            return

        # Walk through trades chronologically and build equity curve
        capital = request.configuration.initial_capital
        equity_curve = [capital]
        daily_returns = []
        trade_results = []

        peak = capital
        max_drawdown = 0
        winners = 0
        losers = 0

        for i, trade in enumerate(trades):
            pnl = float(trade["profit_loss"])
            cost = request.configuration.commission_per_trade
            net_pnl = pnl - cost

            capital += net_pnl
            equity_curve.append(capital)

            if capital > peak:
                peak = capital
            dd = (peak - capital) / peak if peak > 0 else 0
            if dd > max_drawdown:
                max_drawdown = dd

            if net_pnl > 0:
                winners += 1
            elif net_pnl < 0:
                losers += 1

            trade_results.append({
                "trade_number": i + 1,
                "entry_time": trade["entry_time"],
                "exit_time": trade["exit_time"],
                "account_name": trade["account_name"],
                "gross_pnl": pnl,
                "commission": cost,
                "net_pnl": net_pnl,
                "equity_after": capital,
            })

            daily_returns.append(net_pnl)

            # Update progress
            if i % max(1, len(trades) // 10) == 0:
                job["progress"] = 30 + int(50 * (i / len(trades)))
                job["message"] = f"Processing trade {i + 1}/{len(trades)}..."

        job["progress"] = 85
        job["message"] = "Computing statistics..."

        # Compute summary statistics
        total_trades = len(trade_results)
        total_pnl = sum(t["net_pnl"] for t in trade_results)
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        win_rate = winners / total_trades if total_trades > 0 else 0
        avg_winner = (
            sum(t["net_pnl"] for t in trade_results if t["net_pnl"] > 0) / winners
            if winners > 0 else 0
        )
        avg_loser = (
            sum(t["net_pnl"] for t in trade_results if t["net_pnl"] < 0) / losers
            if losers > 0 else 0
        )
        gross_profit = sum(t["net_pnl"] for t in trade_results if t["net_pnl"] > 0)
        gross_loss = abs(sum(t["net_pnl"] for t in trade_results if t["net_pnl"] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Sharpe
        import statistics
        if len(daily_returns) > 1:
            std_dev = statistics.stdev(daily_returns)
            sharpe = (avg_trade / std_dev) if std_dev > 0 else 0
        else:
            sharpe = 0

        results = {
            "backtest_id": job_id,
            "symbol": symbol,
            "method": request.configuration.method,
            "start_date": request.configuration.start_date,
            "end_date": request.configuration.end_date,
            "initial_capital": request.configuration.initial_capital,
            "final_capital": capital,
            "total_return": (capital - request.configuration.initial_capital) / request.configuration.initial_capital,
            "total_pnl": total_pnl,
            "total_trades": total_trades,
            "winning_trades": winners,
            "losing_trades": losers,
            "win_rate": win_rate,
            "avg_trade": avg_trade,
            "avg_winner": avg_winner,
            "avg_loser": avg_loser,
            "profit_factor": profit_factor,
            "sharpe_ratio": sharpe,
            "max_drawdown_pct": max_drawdown,
            "max_drawdown_usd": max_drawdown * request.configuration.initial_capital,
            "equity_curve": [
                {"trade_number": i, "equity": eq}
                for i, eq in enumerate(equity_curve)
            ],
            "trades": trade_results,
            "daily_returns": daily_returns,
        }

        job["results"] = results
        job["status"] = "COMPLETED"
        job["progress"] = 100
        job["message"] = f"Backtest complete — {total_trades} trades, {win_rate:.1%} win rate"
        conn.close()

    except Exception as exc:
        logger.error(f"Backtest job {job_id} failed: {exc}", exc_info=True)
        job["status"] = "FAILED"
        job["error_message"] = str(exc)
        job["progress"] = 0


def _build_results(trades: list, request: BacktestRequest, symbol: str) -> dict:
    """Build a valid (empty) results dict when there are no trades."""
    return {
        "backtest_id": "",
        "symbol": symbol,
        "method": request.configuration.method,
        "start_date": request.configuration.start_date,
        "end_date": request.configuration.end_date,
        "initial_capital": request.configuration.initial_capital,
        "final_capital": request.configuration.initial_capital,
        "total_return": 0,
        "total_pnl": 0,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0,
        "avg_trade": 0,
        "avg_winner": 0,
        "avg_loser": 0,
        "profit_factor": 0,
        "sharpe_ratio": 0,
        "max_drawdown_pct": 0,
        "max_drawdown_usd": 0,
        "equity_curve": [],
        "trades": [],
        "daily_returns": [],
    }


# ── Endpoints ──
@router.post("/run")
async def run_backtest(
    background_tasks: BackgroundTasks,
    request: BacktestRequest = Body(...),
):
    """Launch a backtest job. Returns immediately with a job ID for polling."""
    job_id = str(uuid.uuid4())

    _jobs[job_id] = {
        "backtest_id": job_id,
        "status": "PENDING",
        "progress": 0,
        "message": "Queued...",
        "created_at": time.time(),
        "results": None,
        "error_message": None,
    }

    background_tasks.add_task(_run_backtest_job, job_id, request)

    logger.info(f"Backtest job {job_id} created with {len(request.time_bins)} time bins")

    return {
        "backtest_id": job_id,
        "status": "PENDING",
        "progress": 0,
        "message": "Backtest queued for execution",
    }


@router.get("/status/{backtest_id}")
async def get_backtest_status(backtest_id: str):
    """Poll the status of a running backtest job."""
    job = _jobs.get(backtest_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    return {
        "backtest_id": job["backtest_id"],
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "error_message": job.get("error_message"),
    }


@router.get("/results/{backtest_id}")
async def get_backtest_results(
    backtest_id: str,
    include_trades: bool = True,
    include_daily_returns: bool = True,
):
    """Retrieve the full results of a completed backtest."""
    job = _jobs.get(backtest_id)
    if not job:
        raise HTTPException(status_code=404, detail="Backtest job not found")

    if job["status"] != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail=f"Backtest is not yet completed (status: {job['status']})",
        )

    results = dict(job["results"])

    if not include_trades:
        results.pop("trades", None)
    if not include_daily_returns:
        results.pop("daily_returns", None)

    return results
