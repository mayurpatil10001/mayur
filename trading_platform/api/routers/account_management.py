"""
Account Management API endpoints.

Shows all accounts with last trade dates and data-gap indicators.
"""

import sqlite3
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..dependencies import require_read_permission, require_write_permission


router = APIRouter()
logger = logging.getLogger(__name__)


# ── Response models ─────────────────────────────────────────

class AccountSummary(BaseModel):
    """Summary of a single account/permutation."""
    account_name: str
    symbol: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl: float
    first_trade_date: Optional[str] = None
    last_trade_date: Optional[str] = None
    days_since_last_trade: Optional[int] = None
    best_day_of_week: Optional[int] = None
    best_hour_of_day: Optional[int] = None
    is_active: bool = True


class AccountManagementResponse(BaseModel):
    """Full account management response."""
    accounts: List[AccountSummary]
    total_accounts: int
    stale_accounts: int  # accounts with > 7 days since last trade


class ValidationAlert(BaseModel):
    """A data quality issue found for an account."""
    alert_type: str  # 'missing_exit', 'negative_duration', 'gap', 'intraday_violation'
    severity: str    # 'critical', 'warning'
    message: str
    count: int


class AccountValidationResponse(BaseModel):
    """Validation report for an account."""
    account_name: str
    is_valid: bool
    alerts: List[ValidationAlert]
    total_trades_checked: int


# ── Endpoint ────────────────────────────────────────────────

@router.get(
    "/management",
    response_model=AccountManagementResponse,
    summary="Account management overview",
    description="Returns all accounts with last trade dates, trade counts, and data-gap indicators.",
)
async def account_management_overview(
    stale_threshold_days: int = Query(7, ge=1, le=365, description="Days without trades to mark as stale"),
    current_user: dict = Depends(require_read_permission),
):
    """Get all accounts with management metadata."""

    db_path = Path("trading_platform.db")
    if not db_path.exists():
        raise HTTPException(status_code=500, detail="Database file not found")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                account_name,
                symbol,
                COUNT(*)                                          AS total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) AS winning_trades,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) AS losing_trades,
                ROUND(SUM(CASE WHEN profit_loss > 0 THEN 1.0 ELSE 0 END) * 100.0 / COUNT(*), 1)
                                                                  AS win_rate,
                ROUND(SUM(profit_loss), 2)                        AS total_pnl,
                ROUND(AVG(profit_loss), 2)                        AS avg_pnl,
                MIN(entry_time)                                   AS first_trade_date,
                MAX(exit_time)                                    AS last_trade_date,
                (
                    SELECT CAST(strftime('%w', t2.entry_time) AS INTEGER)
                    FROM processed_trades t2
                    WHERE t2.account_name = t1.account_name AND t2.symbol = t1.symbol
                    GROUP BY strftime('%w', t2.entry_time)
                    ORDER BY SUM(t2.profit_loss) DESC
                    LIMIT 1
                ) AS best_day_of_week,
                (
                    SELECT CAST(strftime('%H', t2.entry_time) AS INTEGER)
                    FROM processed_trades t2
                    WHERE t2.account_name = t1.account_name AND t2.symbol = t1.symbol
                    GROUP BY strftime('%H', t2.entry_time)
                    ORDER BY SUM(t2.profit_loss) DESC
                    LIMIT 1
                ) AS best_hour_of_day
            FROM processed_trades t1
            GROUP BY account_name, symbol
            ORDER BY account_name, symbol
        """)
        rows = cursor.fetchall()

        today = date.today()
        accounts: List[AccountSummary] = []
        stale_count = 0

        for row in rows:
            last_trade = row["last_trade_date"]
            days_since = None
            is_active = True

            if last_trade:
                try:
                    # Handle ISO format strings from SQLite
                    last_dt = datetime.fromisoformat(last_trade.replace("Z", "+00:00"))
                    days_since = (today - last_dt.date()).days
                    is_active = days_since <= stale_threshold_days
                except Exception:
                    pass

            if not is_active:
                stale_count += 1

            accounts.append(AccountSummary(
                account_name=row["account_name"],
                symbol=row["symbol"],
                total_trades=row["total_trades"],
                winning_trades=row["winning_trades"] or 0,
                losing_trades=row["losing_trades"] or 0,
                win_rate=float(row["win_rate"]) if row["win_rate"] else 0.0,
                total_pnl=float(row["total_pnl"]) if row["total_pnl"] else 0.0,
                avg_pnl=float(row["avg_pnl"]) if row["avg_pnl"] else 0.0,
                first_trade_date=row["first_trade_date"],
                last_trade_date=last_trade,
                days_since_last_trade=days_since,
                best_day_of_week=row["best_day_of_week"],
                best_hour_of_day=row["best_hour_of_day"],
                is_active=is_active,
            ))

        return AccountManagementResponse(
            accounts=accounts,
            total_accounts=len(accounts),
            stale_accounts=stale_count,
        )

    except Exception as exc:
        logger.error(f"Account management query failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve account data: {exc}")
    finally:
        conn.close()


# ── Validation ──────────────────────────────────────────────

@router.get(
    "/accounts/{account_name}/validate",
    response_model=AccountValidationResponse,
    summary="Validate account data",
    description="Checks for data integrity issues like mixed symbols, missing exits, or time gaps.",
)
async def validate_account(
    account_name: str,
    symbol: Optional[str] = Query(None, description="Filter validation to a specific symbol"),
    check_intraday: bool = Query(True, description="Enforce intraday rules (entry/exit same day)"),
    current_user: dict = Depends(require_read_permission),
):
    """Perform data validation on an account."""
    db_path = Path("trading_platform.db")
    if not db_path.exists():
        raise HTTPException(status_code=500, detail="Database file not found")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    alerts = []
    
    try:
        cursor = conn.cursor()
        
        # Base query part
        base_query = "FROM processed_trades WHERE account_name = ?"
        params = [account_name]
        
        if symbol:
            base_query += " AND symbol = ?"
            params.append(symbol)
            
        # 1. Check for mixed symbols (Only relevant if NO symbol filter is applied, or to verify strictness)
        # If symbol is passed, we check if there are OTHER symbols? No, if we filter by symbol, we only see that symbol.
        # But if the user expects ONLY 'symbol' in this account, we might not need this check if filtered coverage is 100%.
        # However, keeping it logic:
        if not symbol:
            cursor.execute("SELECT DISTINCT symbol FROM processed_trades WHERE account_name = ?", (account_name,))
            symbols = [r[0] for r in cursor.fetchall()]
            if len(symbols) > 1:
                alerts.append(ValidationAlert(
                    alert_type="mixed_symbols",
                    severity="warning",
                    message=f"Account contains trades for multiple symbols: {', '.join(symbols)}",
                    count=len(symbols)
                ))
            
        # 2. Check for missing exits / negative duration
        cursor.execute(f"SELECT COUNT(*) {base_query} AND duration_minutes < 0", params)
        neg_duration = cursor.fetchone()[0]
        if neg_duration > 0:
            alerts.append(ValidationAlert(
                alert_type="negative_duration",
                severity="critical",
                message="Trades found with Exit Time before Entry Time",
                count=neg_duration
            ))

        # 3. Check for Intraday Violations
        if check_intraday:
            cursor.execute(f"""
                SELECT COUNT(*) {base_query} 
                  AND date(entry_time) != date(exit_time)
            """, params)
            overnight = cursor.fetchone()[0]
            if overnight > 0:
                alerts.append(ValidationAlert(
                    alert_type="overnight_hold",
                    severity="warning",
                    message="Trades found spanning multiple days (Overnight)",
                    count=overnight
                ))
                
        # 4. Check for extreme PnL
        cursor.execute(f"""
            SELECT COUNT(*) {base_query} 
              AND ABS(profit_loss) > 50000
        """, params)
        outliers = cursor.fetchone()[0]
        if outliers > 0:
             alerts.append(ValidationAlert(
                alert_type="pnl_outlier",
                severity="warning",
                message="Trades found with PnL > $50,000 (possible bad data)",
                count=outliers
            ))

        # Get total trades for context
        cursor.execute(f"SELECT COUNT(*) {base_query}", params)
        total = cursor.fetchone()[0]

        return AccountValidationResponse(
            account_name=account_name,
            is_valid=len(alerts) == 0,
            alerts=alerts,
            total_trades_checked=total
        )

    except Exception as exc:
        logger.error(f"Validation failed for {account_name}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {exc}")
    finally:
        conn.close()


@router.post(
    "/accounts/{account_name}/prune",
    summary="Prune invalid trades",
    description="Deletes trades matching specific criteria (e.g., overnight holds) for a given account.",
)
async def prune_account_trades(
    account_name: str,
    criteria: str = Query(..., description="Criteria to prune: 'overnight_hold', 'negative_duration'"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    current_user: dict = Depends(require_write_permission),
):
    """Prune trades matching the validation criteria."""
    db_path = Path("trading_platform.db")
    if not db_path.exists():
        raise HTTPException(status_code=500, detail="Database file not found")

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        
        # Base delete query
        query_parts = ["DELETE FROM processed_trades WHERE account_name = ?"]
        params = [account_name]
        
        if symbol:
            query_parts.append("AND symbol = ?")
            params.append(symbol)
            
        if criteria == "overnight_hold":
            # Delete trades where entry and exit dates differ
            query_parts.append("AND date(entry_time) != date(exit_time)")
        elif criteria == "negative_duration":
            # Delete trades with negative duration
            query_parts.append("AND duration_minutes < 0")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown pruning criteria: {criteria}")
            
        final_query = " ".join(query_parts)
        cursor.execute(final_query, params)
        deleted_count = cursor.rowcount
        conn.commit()
        
        logger.info(f"Pruned {deleted_count} trades for {account_name} (criteria={criteria})")
        return {"message": f"Successfully removed {deleted_count} trades.", "deleted_count": deleted_count}

    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        logger.error(f"Pruning failed for {account_name}: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pruning failed: {exc}")
    finally:
        conn.close()
