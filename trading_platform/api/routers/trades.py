"""
Trade data API endpoints.

This module provides REST endpoints for accessing and managing trade data.

Requirements: 7.1, 10.1, 10.3
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from ..dependencies import (
    get_database_session,
    require_read_permission
)
from ..models.common import APIResponse, PaginatedResponse, PaginationParams
from ..models.trades import (
    TradeResponse,
    TradeListRequest,
    TradeStatsResponse,
    TradeSide
)
from ..exceptions import DataNotFoundException


router = APIRouter()


@router.get(
    "/",
    response_model=APIResponse[PaginatedResponse[TradeResponse]],
    summary="List trades",
    description="Retrieve a paginated list of trades with filtering options."
)
async def list_trades(
    pagination: PaginationParams = Depends(),
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    start_date: Optional[datetime] = Query(None, description="Filter trades from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter trades until this date"),
    min_profit: Optional[float] = Query(None, description="Filter trades with profit >= this amount"),
    max_profit: Optional[float] = Query(None, description="Filter trades with profit <= this amount"),
    side: Optional[TradeSide] = Query(None, description="Filter by trade side"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[PaginatedResponse[TradeResponse]]:
    """List trades with pagination and filtering."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[TRADES API] Listing trades - account={account_name}, symbol={symbol}, page={pagination.page}")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Build query
        query = """
        SELECT 
            trade_id,
            account_name,
            symbol,
            entry_time,
            exit_time,
            entry_price,
            exit_price,
            quantity,
            side,
            profit_loss,
            commission,
            duration_minutes,
            hour_of_day,
            day_of_week
        FROM processed_trades
        WHERE 1=1
        """
        params = []
        
        if account_name:
            query += " AND account_name = ?"
            params.append(account_name)
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
            
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date.isoformat())
            
        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date.isoformat())
            
        if side:
            query += " AND side = ?"
            params.append(side.value if hasattr(side, 'value') else side)
            
        # Get total count for pagination
        count_query = f"SELECT COUNT(*) FROM ({query})"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]
        
        # Apply sorting and pagination
        query += " ORDER BY entry_time DESC LIMIT ? OFFSET ?"
        params.extend([pagination.size, pagination.offset])
        
        logger.info(f"[TRADES API] Executing query: {query}")
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        trades = []
        for row in rows:
            # Calculate time slot matching the hourly breakdown logic
            dt = datetime.fromisoformat(row['entry_time']) if isinstance(row['entry_time'], str) else row['entry_time']
            # We use the raw hour/minute as stored in DB (string-based strftime behavior)
            # Since fromisoformat preserves the numbers, we can just extract them
            slot_hour = dt.hour
            slot_minute = 0 if dt.minute < 30 else 30
            time_slot = f"{slot_hour:02d}:{slot_minute:02d}"

            trades.append(TradeResponse(
                trade_id=row['trade_id'],
                time_slot=time_slot,
                account_name=row['account_name'],
                symbol=row['symbol'],
                entry_time=dt,
                exit_time=datetime.fromisoformat(row['exit_time']) if isinstance(row['exit_time'], str) else row['exit_time'],
                entry_price=row['entry_price'],
                exit_price=row['exit_price'],
                quantity=row['quantity'],
                side=TradeSide.LONG if row['side'] == 'LONG' else TradeSide.SHORT,
                profit_loss=row['profit_loss'],
                commission=row['commission'],
                duration_minutes=row['duration_minutes'],
                hour_of_day=row['hour_of_day'],
                day_of_week=row['day_of_week']
            ))
            
        conn.close()
        
        paginated_response = PaginatedResponse[TradeResponse](
            items=trades,
            total=total_count,
            page=pagination.page,
            size=pagination.size,
            pages=(total_count + pagination.size - 1) // pagination.size,
            has_next=pagination.offset + pagination.size < total_count,
            has_prev=pagination.page > 1
        )
        
        return APIResponse[PaginatedResponse[TradeResponse]](
            status="success",
            message=f"Retrieved {len(trades)} trades",
            data=paginated_response
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trades: {str(e)}")


@router.get(
    "/{trade_id}",
    response_model=APIResponse[TradeResponse],
    summary="Get trade details",
    description="Retrieve detailed information for a specific trade."
)
async def get_trade(
    trade_id: str = Path(..., description="Trade ID"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[TradeResponse]:
    """Get detailed information for a specific trade."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    
    try:
        db_path = Path("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM processed_trades WHERE trade_id = ?", (trade_id,))
        row = cursor.fetchone()
        
        if not row:
            raise DataNotFoundException("Trade", trade_id)
            
        dt = datetime.fromisoformat(row['entry_time']) if isinstance(row['entry_time'], str) else row['entry_time']
        slot_hour = dt.hour
        slot_minute = 0 if dt.minute < 30 else 30
        time_slot = f"{slot_hour:02d}:{slot_minute:02d}"

        trade = TradeResponse(
            trade_id=row['trade_id'],
            time_slot=time_slot,
            account_name=row['account_name'],
            symbol=row['symbol'],
            entry_time=dt,
            exit_time=datetime.fromisoformat(row['exit_time']) if isinstance(row['exit_time'], str) else row['exit_time'],
            entry_price=row['entry_price'],
            exit_price=row['exit_price'],
            quantity=row['quantity'],
            side=TradeSide.LONG if row['side'] == 'LONG' else TradeSide.SHORT,
            profit_loss=row['profit_loss'],
            commission=row['commission'],
            duration_minutes=row['duration_minutes'],
            hour_of_day=row['hour_of_day'],
            day_of_week=row['day_of_week']
        )
        
        conn.close()
        
        return APIResponse[TradeResponse](
            status="success",
            message=f"Retrieved trade {trade_id}",
            data=trade
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Trade {trade_id} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trade: {str(e)}")


@router.get(
    "/stats/{account_name}",
    response_model=APIResponse[TradeStatsResponse],
    summary="Get trade statistics",
    description="Get statistical summary of trades for an account."
)
async def get_trade_stats(
    account_name: str = Path(..., description="Account name"),
    start_date: Optional[datetime] = Query(None, description="Filter trades from this date"),
    end_date: Optional[datetime] = Query(None, description="Filter trades until this date"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[TradeStatsResponse]:
    """Get trade statistics for an account."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    
    try:
        db_path = Path("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "FROM processed_trades WHERE account_name = ?"
        params = [account_name]
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        
        if start_date:
            query += " AND entry_time >= ?"
            params.append(start_date.isoformat())
            
        if end_date:
            query += " AND entry_time <= ?"
            params.append(end_date.isoformat())
            
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit_loss <= 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(profit_loss) as total_pnl,
                AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END) as avg_win,
                AVG(CASE WHEN profit_loss <= 0 THEN profit_loss ELSE NULL END) as avg_loss,
                MAX(profit_loss) as largest_win,
                MIN(profit_loss) as largest_loss,
                AVG(duration_minutes) as avg_duration,
                SUM(CASE WHEN profit_loss > 0 THEN profit_loss ELSE 0 END) as gross_profit,
                ABS(SUM(CASE WHEN profit_loss < 0 THEN profit_loss ELSE 0 END)) as gross_loss
            {query}
        """, params)
        
        row = cursor.fetchone()
        
        if not row or row['total_trades'] == 0:
            stats = TradeStatsResponse(
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                total_profit_loss=0.0,
                average_win=0.0,
                average_loss=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                profit_factor=0.0,
                average_duration_minutes=0.0
            )
        else:
            win_rate = (row['winning_trades'] / row['total_trades'] * 100)
            profit_factor = (row['gross_profit'] / row['gross_loss']) if row['gross_loss'] > 0 else 0.0
            
            stats = TradeStatsResponse(
                total_trades=row['total_trades'],
                winning_trades=row['winning_trades'],
                losing_trades=row['losing_trades'],
                win_rate=win_rate,
                total_profit_loss=row['total_pnl'] or 0.0,
                average_win=row['avg_win'] or 0.0,
                average_loss=row['avg_loss'] or 0.0,
                largest_win=row['largest_win'] or 0.0,
                largest_loss=row['largest_loss'] or 0.0,
                profit_factor=profit_factor,
                average_duration_minutes=row['avg_duration'] or 0.0
            )
            
        conn.close()
        
        return APIResponse[TradeStatsResponse](
            status="success",
            message=f"Retrieved trade statistics for {account_name}",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trade statistics: {str(e)}")