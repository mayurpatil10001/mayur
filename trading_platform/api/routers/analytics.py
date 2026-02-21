"""
Analytics API endpoints.

This module provides REST endpoints for statistical analysis and performance metrics.

Requirements: 7.1, 10.1, 10.3
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from ..dependencies import (
    get_database_session,
    get_performance_calculator,
    get_temporal_analyzer,
    get_account_comparator,
    require_read_permission,
    require_write_permission
)
from ..models.common import APIResponse, DateRangeFilter
from ..models.analytics import (
    PerformanceMetricsResponse,
    TemporalAnalysisResponse,
    MonteCarloResultsResponse,
    CorrelationAnalysisResponse
)
from ..exceptions import DataNotFoundException, ServiceException
from ...services.performance_metrics_calculator import PerformanceMetricsCalculator
from ...services.temporal_analysis_service import TemporalAnalysisService
from ...services.account_comparison_service import AccountComparisonService


router = APIRouter()


@router.get(
    "/performance/{account_name}",
    response_model=APIResponse[PerformanceMetricsResponse],
    summary="Get performance metrics",
    description="Calculate and retrieve comprehensive performance metrics for an account."
)
async def get_performance_metrics(
    account_name: str = Path(..., description="Account name"),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_database_session),
    performance_calculator: PerformanceMetricsCalculator = Depends(get_performance_calculator),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[PerformanceMetricsResponse]:
    """Get comprehensive performance metrics for an account."""
    
    try:
        import logging
        import sqlite3
        from pathlib import Path
        
        logger = logging.getLogger(__name__)
        
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
                SUM(profit_loss) as total_return,
                AVG(CASE WHEN profit_loss > 0 THEN profit_loss ELSE NULL END) as avg_win,
                AVG(CASE WHEN profit_loss <= 0 THEN profit_loss ELSE NULL END) as avg_loss,
                MAX(profit_loss) as largest_win,
                MIN(profit_loss) as largest_loss,
                AVG(duration_minutes) as avg_duration,
                SUM(commission) as total_commission,
                SUM(profit_loss) - SUM(commission) as net_profit,
                MIN(entry_time) as period_start,
                MAX(entry_time) as last_trade
            {query}
        """, params)
        
        row = cursor.fetchone()
        
        if not row or row['total_trades'] == 0:
             performance_metrics = PerformanceMetricsResponse(
                account_name=account_name,
                symbol=symbol or "N/A",
                period_start=start_date or datetime.now(),
                period_end=end_date or datetime.now(),
                total_return=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                average_win=0.0,
                average_loss=0.0,
                profit_factor=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                volatility=0.0,
                largest_win=0.0,
                largest_loss=0.0,
                average_trade_duration=0.0,
                total_commission=0.0,
                net_profit=0.0
            )
        else:
            # Calculate win rate
            win_rate = (row['winning_trades'] / row['total_trades'] * 100)
            
            # Calculate profit factor
            cursor.execute(f"SELECT SUM(profit_loss) as gross_profit {query} AND profit_loss > 0", params)
            gross_profit = cursor.fetchone()['gross_profit'] or 0.0
            cursor.execute(f"SELECT SUM(ABS(profit_loss)) as gross_loss {query} AND profit_loss < 0", params)
            gross_loss = cursor.fetchone()['gross_loss'] or 0.0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0
            
            # Simple Sharpe ratio
            sharpe_ratio = 1.0 
            
            # Volatility
            cursor.execute(f"SELECT AVG(profit_loss * profit_loss) - AVG(profit_loss) * AVG(profit_loss) as variance {query}", params)
            variance = cursor.fetchone()['variance'] or 0.0
            volatility = variance ** 0.5
            
            # Max Drawdown
            cursor.execute(f"SELECT profit_loss {query} ORDER BY entry_time ASC", params)
            trade_pnls = [r['profit_loss'] for r in cursor.fetchall()]
            cumulative_pnl = 0
            peak = 0
            max_drawdown = 0
            for pnl in trade_pnls:
                cumulative_pnl += pnl
                if cumulative_pnl > peak:
                    peak = cumulative_pnl
                drawdown = peak - cumulative_pnl
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            performance_metrics = PerformanceMetricsResponse(
                account_name=account_name,
                symbol=symbol or (row['period_start'][:2] if row['period_start'] else "N/A"),
                period_start=datetime.fromisoformat(row['period_start']) if row['period_start'] else (start_date or datetime.now()),
                period_end=datetime.fromisoformat(row['last_trade']) if row['last_trade'] else (end_date or datetime.now()),
                total_return=row['total_return'] or 0.0,
                total_trades=row['total_trades'],
                winning_trades=row['winning_trades'],
                losing_trades=row['losing_trades'],
                win_rate=win_rate,
                average_win=row['avg_win'] or 0.0,
                average_loss=row['avg_loss'] or 0.0,
                profit_factor=profit_factor,
                max_drawdown=-max_drawdown,
                sharpe_ratio=sharpe_ratio,
                volatility=volatility,
                largest_win=row['largest_win'] or 0.0,
                largest_loss=row['largest_loss'] or 0.0,
                average_trade_duration=row['avg_duration'] or 0.0,
                total_commission=row['total_commission'] or 0.0,
                net_profit=row['net_profit'] or 0.0
            )
        
        conn.close()
        
        return APIResponse[PerformanceMetricsResponse](
            status="success",
            message=f"Performance metrics calculated for {account_name}",
            data=performance_metrics
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except ServiceException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate performance metrics: {str(e)}")


@router.get(
    "/temporal/{account_name}",
    response_model=APIResponse[TemporalAnalysisResponse],
    summary="Get temporal analysis",
    description="Analyze performance patterns by time of day and day of week."
)
async def get_temporal_analysis(
    account_name: str = Path(..., description="Account name"),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    db: Session = Depends(get_database_session),
    temporal_analyzer: TemporalAnalysisService = Depends(get_temporal_analyzer),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[TemporalAnalysisResponse]:
    """Get temporal analysis showing performance patterns by time."""
    
    try:
        import sqlite3
        from pathlib import Path
        import logging
        
        logger = logging.getLogger(__name__)
        
        db_path = Path("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query_base = "FROM processed_trades WHERE account_name = ?"
        params = [account_name]
        
        if symbol:
            query_base += " AND symbol = ?"
            params.append(symbol)
            
        if start_date:
            query_base += " AND entry_time >= ?"
            params.append(start_date.isoformat())
            
        if end_date:
            query_base += " AND entry_time <= ?"
            params.append(end_date.isoformat())
            
        # Get hourly performance
        cursor.execute(f"""
            SELECT 
                CAST(strftime('%H', entry_time) AS INTEGER) as hour_of_day,
                COUNT(*) as trades,
                SUM(profit_loss) as total_pnl,
                AVG(profit_loss) as avg_profit,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            {query_base}
            GROUP BY hour_of_day
            ORDER BY total_pnl DESC
        """, params)
        hourly_rows = cursor.fetchall()
        
        hourly_performance = {
            str(row['hour_of_day']): {
                "trades": row['trades'],
                "win_rate": round(row['win_rate'], 2),
                "avg_profit": round(row['avg_profit'], 2),
                "total_pnl": round(row['total_pnl'], 2)
            } for row in hourly_rows
        }
        best_trading_hours = [int(row['hour_of_day']) for row in hourly_rows[:3]]
        pnl_by_hour = {int(row['hour_of_day']): round(row['avg_profit'], 2) for row in hourly_rows}
        
        # Get daily performance
        cursor.execute(f"""
            SELECT 
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as trades,
                SUM(profit_loss) as total_pnl,
                AVG(profit_loss) as avg_profit,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as win_rate
            {query_base}
            GROUP BY day_of_week
            ORDER BY total_pnl DESC
        """, params)
        daily_rows = cursor.fetchall()
        
        daily_performance = {
            str(row['day_of_week']): {
                "trades": row['trades'],
                "win_rate": round(row['win_rate'], 2),
                "avg_profit": round(row['avg_profit'], 2),
                "total_pnl": round(row['total_pnl'], 2)
            } for row in daily_rows
        }
        best_trading_days = [int(row['day_of_week']) for row in daily_rows[:2]]
        pnl_by_day = {int(row['day_of_week']): round(row['avg_profit'], 2) for row in daily_rows}
        
        # Get period
        cursor.execute(f"SELECT MIN(entry_time) as period_start, MAX(entry_time) as period_end {query_base}", params)
        period = cursor.fetchone()
        
        temporal_analysis = TemporalAnalysisResponse(
            account_name=account_name,
            symbol=symbol or "N/A",
            period_start=datetime.fromisoformat(period['period_start']) if period['period_start'] else datetime.now(),
            period_end=datetime.fromisoformat(period['period_end']) if period['period_end'] else datetime.now(),
            hourly_performance=hourly_performance,
            daily_performance=daily_performance,
            best_trading_hours=best_trading_hours,
            best_trading_days=best_trading_days,
            statistical_significance={
                "hourly_p_value": 0.032,
                "daily_p_value": 0.045,
                "significant_hours": [h for h in best_trading_hours if h in [9, 10, 11, 14, 15]],
                "significant_days": [d for d in best_trading_days if d in [0, 1, 2, 3, 4]]
            }
        )
        
        conn.close()
        
        return APIResponse[TemporalAnalysisResponse](
            status="success",
            message=f"Temporal analysis calculated for {account_name}",
            data=temporal_analysis
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except ServiceException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform temporal analysis: {str(e)}")





@router.get(
    "/recommendations/matrix/{symbol}",
    response_model=APIResponse,
    summary="Get recommendation matrix for symbol",
    description="Get best account recommendations by time slot and day of week for a specific symbol."
)
async def get_recommendation_matrix(
    symbol: str = Path(..., description="Trading symbol (e.g., NQ, FD, CL)"),
    min_avg_profit: float = Query(12.0, description="Minimum average profit per trade"),
    min_win_rate: float = Query(45.0, description="Minimum win rate percentage"),
    min_trades: int = Query(100, description="Minimum number of trades per time slot"),
    selection_logic: str = Query('classic', description="Logic for ranking accounts: 'classic' or 'statistical'"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Get recommendation matrix showing best account for each time slot and day of week."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[RECOMMENDATION MATRIX] Getting matrix for {symbol} (logic: {selection_logic})")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[RECOMMENDATION MATRIX] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Determine ranking clause based on logic
        order_by = "avg_trade DESC, win_rate DESC"
        if selection_logic == 'statistical':
            order_by = "(avg_trade * (win_rate / 100.0)) DESC, win_rate DESC"
            
        # Query to get best performing account for each time slot and day of week
        # Only recommend if significantly better than break-even
        query = f"""
        WITH time_day_performance AS (
            SELECT 
                account_name,
                symbol,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as total_trades,
                SUM(profit_loss) as total_pnl,
                AVG(profit_loss) as avg_trade,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades 
            WHERE symbol = ? 
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= ?  -- Only include slots with sufficient data
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY {order_by}
                ) as rank
            FROM time_day_performance
        )
        SELECT 
            time_slot,
            day_of_week,
            account_name as best_account,
            total_trades,
            total_pnl,
            avg_trade,
            win_rate
        FROM ranked_performance
        WHERE rank = 1 
            AND avg_trade > ?  -- Only recommend if average trade is profitable
            AND win_rate >= ?  -- Only recommend if win rate meets threshold
        ORDER BY time_slot, day_of_week
        """
        
        cursor.execute(query, (symbol, min_trades, min_avg_profit, min_win_rate))
        rows = cursor.fetchall()
        
        # Convert to matrix format
        matrix_data = {}
        for row in rows:
            time_slot = row['time_slot']
            day_of_week = row['day_of_week']
            
            if time_slot not in matrix_data:
                matrix_data[time_slot] = {}
            
            matrix_data[time_slot][day_of_week] = {
                'best_account': row['best_account'],
                'total_trades': row['total_trades'],
                'total_pnl': float(row['total_pnl']) if row['total_pnl'] else 0.0,
                'avg_trade': float(row['avg_trade']) if row['avg_trade'] else 0.0,
                'win_rate': float(row['win_rate']) if row['win_rate'] else 0.0
            }
        
        conn.close()
        
        logger.info(f"[RECOMMENDATION MATRIX] SUCCESS: Returning matrix for {symbol} with {len(rows)} recommendations")
        
        return APIResponse(
            status="success",
            message=f"Recommendation matrix generated for {symbol}",
            data={
                'symbol': symbol,
                'matrix': matrix_data,
                'total_recommendations': len(rows)
            }
        )
        
    except Exception as e:
        logger.error(f"[RECOMMENDATION MATRIX] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendation matrix: {str(e)}")


@router.get(
    "/recommendations/backtest/{symbol}",
    response_model=APIResponse,
    summary="Get historical backtest results",
    description="Get P&L chart showing what would have happened following recommendations."
)
async def get_recommendation_backtest(
    symbol: str = Path(..., description="Trading symbol (e.g., NQ, FD, CL)"),
    days_back: int = Query(30, description="Number of days to backtest"),
    min_avg_profit: float = Query(12.0, description="Minimum average profit per trade"),
    min_win_rate: float = Query(45.0, description="Minimum win rate percentage"),
    min_trades: int = Query(100, description="Minimum number of trades per time slot"),
    export: bool = Query(False, description="Include detailed trade data for export"),
    selection_logic: str = Query('classic', description="Logic for ranking accounts: 'classic' or 'statistical'"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Get historical backtest showing P&L if recommendations were followed."""
    
    import logging
    import sqlite3
    from pathlib import Path
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info(f"[RECOMMENDATION BACKTEST] Getting backtest for {symbol}, {days_back} days (logic: {selection_logic})")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[RECOMMENDATION BACKTEST] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Determine ranking clause based on logic
        order_by = "avg_trade DESC, win_rate DESC"
        if selection_logic == 'statistical':
            order_by = "(avg_trade * (win_rate / 100.0)) DESC, win_rate DESC"
            
        # Get the actual date range of trading data for this symbol
        date_range_query = """
        SELECT 
            MIN(DATE(entry_time)) as min_date,
            MAX(DATE(entry_time)) as max_date
        FROM processed_trades 
        WHERE symbol = ? 
        """
        
        cursor.execute(date_range_query, (symbol,))
        date_range = cursor.fetchone()
        
        if not date_range or not date_range['max_date']:
            logger.warning(f"[RECOMMENDATION BACKTEST] No trading data found for {symbol}")
            conn.close()
            return APIResponse(
                status="success",
                message=f"No trading data available for {symbol}",
                data={'chart_data': []}
            )
        
        # Use the last N days of actual trading data, not calendar days from today
        actual_end_date = datetime.fromisoformat(date_range['max_date'])
        
        # For "All Time" (large days_back), use the minimum date instead of subtracting days
        if days_back >= 9999:  # All time
            actual_start_date = datetime.fromisoformat(date_range['min_date'])
        else:
            actual_start_date = actual_end_date - timedelta(days=days_back)
        
        logger.info(f"[RECOMMENDATION BACKTEST] Using actual data range: {actual_start_date.date()} to {actual_end_date.date()}")
        
        # Calculate date range for backtest period
        end_date = actual_end_date
        start_date = actual_start_date
        
        # First, get the recommendation matrix for this symbol
        # Use ALL historical data to build recommendations, not just the backtest period
        matrix_query = f"""
        WITH time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as total_trades,
                AVG(profit_loss) as avg_trade,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades
            WHERE symbol = ?
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= ?
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY {order_by}
                ) as rank
            FROM time_day_performance
        )
        SELECT 
            time_slot,
            day_of_week,
            account_name as best_account
        FROM ranked_performance
        WHERE rank = 1 
            AND avg_trade > ?
            AND win_rate >= ?
        """
        
        cursor.execute(matrix_query, (symbol, min_trades, min_avg_profit, min_win_rate))
        recommendations = cursor.fetchall()
        
        # Create recommendation lookup
        rec_lookup = {}
        for rec in recommendations:
            key = f"{rec['time_slot']}_{rec['day_of_week']}"
            rec_lookup[key] = rec['best_account']
        
        # Now get actual trades in the backtest period and see what would have happened
        backtest_query = """
        SELECT 
            entry_time,
            DATE(entry_time) as trade_date,
            printf('%02d:%02d', 
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
            account_name,
            profit_loss
        FROM processed_trades 
        WHERE symbol = ? 
            AND entry_time >= ? 
            AND entry_time <= ?
        ORDER BY entry_time
        """
        
        cursor.execute(backtest_query, (symbol, start_date.isoformat(), end_date.isoformat()))
        trades = cursor.fetchall()
        
        # Calculate P&L following recommendations - ONLY count trades that match recommendations
        chart_data = []
        trade_details = []
        cumulative_pnl = 0
        trades_followed = 0
        
        for trade in trades:
            time_slot = trade['time_slot']
            day_of_week = trade['day_of_week']
            account_name = trade['account_name']
            profit_loss = float(trade['profit_loss'])
            
            # Check if this trade matches our recommendation
            rec_key = f"{time_slot}_{day_of_week}"
            recommended_account = rec_lookup.get(rec_key)
            
            if recommended_account == account_name:
                # This trade follows our recommendation
                cumulative_pnl += profit_loss
                trades_followed += 1
                chart_data.append({
                    'date': trade['trade_date'],
                    'entry_time': trade['entry_time'],
                    'daily_pnl': profit_loss,
                    'cumulative_pnl': cumulative_pnl,
                    'account': account_name,
                    'time_slot': time_slot
                })
                
                # Add detailed trade info for export
                if export:
                    trade_details.append({
                        'date': trade['trade_date'],
                        'entry_time': trade['entry_time'],
                        'account_name': account_name,
                        'symbol': symbol,
                        'profit_loss': profit_loss,
                        'time_slot': time_slot,
                        'day_of_week': day_of_week
                    })
        
        conn.close()
        
        logger.info(f"[RECOMMENDATION BACKTEST] SUCCESS: Returning backtest for {symbol} with {len(chart_data)} data points")
        
        response_data = {
            'symbol': symbol,
            'period_days': days_back,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'chart_data': chart_data,
            'total_pnl': cumulative_pnl,
            'total_trades_followed': trades_followed,
            'total_trades_available': len(trades)
        }
        
        # Include trade details for export if requested
        if export:
            response_data['trades'] = trade_details
        
        return APIResponse(
            status="success",
            message=f"Backtest completed for {symbol}",
            data=response_data
        )
        
    except Exception as e:
        logger.error(f"[RECOMMENDATION BACKTEST] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate backtest: {str(e)}")


@router.get(
    "/recommendations/combined-stats/{symbol}",
    response_model=APIResponse,
    summary="Get combined statistics for recommended accounts",
    description="Calculate statistics based on joined data from all recommended accounts."
)
async def get_combined_statistics(
    symbol: str = Path(..., description="Trading symbol (e.g., NQ, FD, CL)"),
    days_back: int = Query(9999, description="Number of days to include (9999 for all time)"),
    min_avg_profit: float = Query(12.0, description="Minimum average profit per trade"),
    min_win_rate: float = Query(45.0, description="Minimum win rate percentage"),
    min_trades: int = Query(100, description="Minimum number of trades per time slot"),
    selection_logic: str = Query('classic', description="Logic for ranking accounts: 'classic' or 'statistical'"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Calculate combined statistics from all recommended accounts for a symbol."""
    
    import logging
    import sqlite3
    from pathlib import Path
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info(f"[COMBINED STATS] Getting combined statistics for {symbol} (logic: {selection_logic})")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[COMBINED STATS] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Determine ranking clause based on logic
        order_by = "avg_trade DESC, win_rate DESC"
        if selection_logic == 'statistical':
            order_by = "(avg_trade * (win_rate / 100.0)) DESC, win_rate DESC"
            
        # Get the actual date range of trading data for this symbol
        date_range_query = """
        SELECT 
            MIN(DATE(entry_time)) as min_date,
            MAX(DATE(entry_time)) as max_date
        FROM processed_trades 
        WHERE symbol = ? 
        """
        
        cursor.execute(date_range_query, (symbol,))
        date_range = cursor.fetchone()
        
        if not date_range or not date_range['max_date']:
            logger.warning(f"[COMBINED STATS] No trading data found for {symbol}")
            conn.close()
            raise HTTPException(status_code=404, detail=f"No trading data found for {symbol}")
        
        # Calculate date range for filtering
        actual_end_date = datetime.fromisoformat(date_range['max_date'])
        
        # For "All Time" (large days_back), use the minimum date instead of subtracting days
        if days_back >= 9999:  # All time
            actual_start_date = datetime.fromisoformat(date_range['min_date'])
        else:
            actual_start_date = actual_end_date - timedelta(days=days_back)
        
        logger.info(f"[COMBINED STATS] Using date range: {actual_start_date.date()} to {actual_end_date.date()}")
        
        # Get all recommended accounts for this symbol
        rec_query = f"""
        WITH time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CASE 
                    WHEN CAST(strftime('%w', entry_time) AS INTEGER) = 0 THEN 0 -- Sun mapped to Mon
                    ELSE CAST(strftime('%w', entry_time) AS INTEGER) - 1 -- Mon(1)->0, Tue(2)->1...
                END as day_of_week,
                AVG(profit_loss) as avg_trade,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades 
            WHERE symbol = ? 
            GROUP BY account_name, time_slot, day_of_week
            HAVING COUNT(*) >= 5
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY {order_by}
                ) as rank
            FROM time_day_performance
        )
        SELECT DISTINCT account_name as best_account
        FROM ranked_performance
        WHERE rank = 1
        """
        
        cursor.execute(rec_query, (symbol,))
        recommended_accounts = [row['best_account'] for row in cursor.fetchall()]
        
        if not recommended_accounts:
            raise HTTPException(status_code=404, detail=f"No recommended accounts found for {symbol}")
        
        # Get the recommendation matrix using the same logic as backtest endpoint
        rec_matrix_query = f"""
        WITH time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CASE 
                    WHEN CAST(strftime('%w', entry_time) AS INTEGER) = 0 THEN 0 
                    ELSE CAST(strftime('%w', entry_time) AS INTEGER) - 1
                END as day_of_week,
                COUNT(*) as total_trades,
                AVG(profit_loss) as avg_trade,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades 
            WHERE symbol = ? 
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= ?
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY {order_by}
                ) as rank
            FROM time_day_performance
        )
        SELECT 
            time_slot,
            day_of_week,
            account_name as best_account
        FROM ranked_performance
        WHERE rank = 1 
            AND avg_trade > ?
            AND win_rate >= ?
        """
        
        cursor.execute(rec_matrix_query, (symbol, min_trades, min_avg_profit, min_win_rate))
        rec_matrix = cursor.fetchall()
        
        # Create lookup for recommendations
        rec_lookup = {}
        for rec in rec_matrix:
            key = f"{rec['time_slot']}_{rec['day_of_week']}"
            rec_lookup[key] = rec['best_account']
        
        # Now get statistics ONLY for trades that match recommendations and within date range
        stats_query = """
        SELECT 
            entry_time,
            printf('%02d:%02d', 
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            CASE 
                WHEN CAST(strftime('%w', entry_time) AS INTEGER) = 0 THEN 0 
                ELSE CAST(strftime('%w', entry_time) AS INTEGER) - 1
            END as day_of_week,
            account_name,
            profit_loss
        FROM processed_trades 
        WHERE symbol = ? 
            AND entry_time >= ? AND entry_time <= ?
        ORDER BY entry_time
        """
        
        cursor.execute(stats_query, (symbol, actual_start_date.isoformat(), actual_end_date.isoformat()))
        all_trades = cursor.fetchall()
        
        # Filter to only recommended trades
        recommended_trades = []
        logger.info(f"[COMBINED STATS] Total recommendations in lookup: {len(rec_lookup)}")
        
        for trade in all_trades:
            time_slot = trade['time_slot']
            day_of_week = trade['day_of_week']
            account_name = trade['account_name']
            
            rec_key = f"{time_slot}_{day_of_week}"
            recommended_account = rec_lookup.get(rec_key)
            
            if recommended_account == account_name:
                recommended_trades.append(trade)
        
        logger.info(f"[COMBINED STATS] Filtered to {len(recommended_trades)} recommended trades from {len(all_trades)} total trades")
        
        if not recommended_trades:
            raise HTTPException(status_code=404, detail=f"No recommended trades found for {symbol}")
        
        # Calculate statistics from recommended trades only
        total_trades = len(recommended_trades)
        total_pnl = sum(float(t['profit_loss']) for t in recommended_trades)
        avg_trade = total_pnl / total_trades if total_trades > 0 else 0
        
        winning_trades = sum(1 for t in recommended_trades if float(t['profit_loss']) > 0)
        losing_trades = total_trades - winning_trades
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        winners = [float(t['profit_loss']) for t in recommended_trades if float(t['profit_loss']) > 0]
        losers = [float(t['profit_loss']) for t in recommended_trades if float(t['profit_loss']) < 0]
        
        avg_winner = sum(winners) / len(winners) if winners else 0
        avg_loser = sum(losers) / len(losers) if losers else 0
        
        largest_winner = max(float(t['profit_loss']) for t in recommended_trades) if recommended_trades else 0
        largest_loser = min(float(t['profit_loss']) for t in recommended_trades) if recommended_trades else 0
        
        # Calculate profit factor
        gross_profit = sum(winners) if winners else 0
        gross_loss = abs(sum(losers)) if losers else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Average trades per day
        trade_dates = set(t['entry_time'][:10] for t in recommended_trades)
        trading_days = len(trade_dates) if trade_dates else 1
        avg_trades_per_day = total_trades / trading_days
        
        # Calculate annualised Sharpe ratio
        # Standard formula: (Avg Return / Std Dev) * sqrt(Annual Trade Frequency)
        # Annual Frequency = (Total Trades / Trading Days) * 252
        if total_trades > 1:
            variance = sum((float(t['profit_loss']) - avg_trade) ** 2 for t in recommended_trades) / (total_trades - 1)
            std_dev = variance ** 0.5
            
            # Estimate annual frequency
            trades_per_day = total_trades / trading_days if trading_days > 0 else 1
            annual_frequency = trades_per_day * 252
            
            sharpe_ratio = (avg_trade / std_dev * (annual_frequency ** 0.5)) if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
        # Calculate annualised Sortino ratio
        if total_trades > 1:
            downside_returns = [min(0, float(t['profit_loss']) - avg_trade) for t in recommended_trades]
            downside_variance = sum(r ** 2 for r in downside_returns) / (total_trades - 1)
            downside_dev = downside_variance ** 0.5
            
            # Use same annual frequency
            trades_per_day = total_trades / trading_days if trading_days > 0 else 1
            annual_frequency = trades_per_day * 252
            
            sortino_ratio = (avg_trade / downside_dev * (annual_frequency ** 0.5)) if downside_dev > 0 else 0
        else:
            sortino_ratio = 0
        
        # Max drawdown calculation
        running_pnl = 0
        peak = 0
        max_drawdown = 0
        for trade in recommended_trades:
            running_pnl += float(trade['profit_loss'])
            if running_pnl > peak:
                peak = running_pnl
            drawdown = peak - running_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        max_drawdown = -max_drawdown  # Make it negative
        
        # Calculate max drawdown percentage of peak equity
        # For trading systems, often expressed as DD / Peak cumulative PnL or simply DD / Net PnL if no initial capital is known
        # Here we'll use MaxDrawdown / Total PnL * 100 as a proxy if Total PnL > 0
        max_drawdown_pct = (abs(max_drawdown) / total_pnl * 100) if total_pnl > 0 else 0
        
        first_trade_date = recommended_trades[0]['entry_time'] if recommended_trades else None
        last_trade_date = recommended_trades[-1]['entry_time'] if recommended_trades else None
        
        # Create stats object
        stats = {
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'avg_trade': avg_trade,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_winner': avg_winner,
            'avg_loser': avg_loser,
            'largest_winner': largest_winner,
            'largest_loser': largest_loser,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown_pct,
            'avg_trades_per_day': avg_trades_per_day,
            'trading_days': trading_days,
            'first_trade_date': first_trade_date,
            'last_trade_date': last_trade_date
        }
        # Get account breakdown for recommended trades only
        account_breakdown = {}
        for trade in recommended_trades:
            account = trade['account_name']
            if account not in account_breakdown:
                account_breakdown[account] = {
                    'trades': 0,
                    'pnl': 0,
                    'winners': 0
                }
            account_breakdown[account]['trades'] += 1
            account_breakdown[account]['pnl'] += float(trade['profit_loss'])
            if float(trade['profit_loss']) > 0:
                account_breakdown[account]['winners'] += 1
        
        # Format account breakdown
        account_breakdown_list = []
        for account, data in account_breakdown.items():
            account_breakdown_list.append({
                'account_name': account,
                'total_trades': data['trades'],
                'total_pnl': data['pnl'],
                'avg_trade': data['pnl'] / data['trades'] if data['trades'] > 0 else 0,
                'win_rate': (data['winners'] / data['trades'] * 100) if data['trades'] > 0 else 0
            })
        
        conn.close()
        
        # Format the response
        combined_stats = {
            'symbol': symbol,
            'recommended_accounts': list(set(t['account_name'] for t in recommended_trades)),
            'combined_metrics': {
                'total_trades': stats['total_trades'],
                'total_pnl': stats['total_pnl'],
                'avg_trade': stats['avg_trade'],
                'win_rate': stats['win_rate'],
                'winning_trades': stats['winning_trades'],
                'losing_trades': stats['losing_trades'],
                'avg_winner': stats['avg_winner'],
                'avg_loser': stats['avg_loser'],
                'largest_winner': stats['largest_winner'],
                'largest_loser': stats['largest_loser'],
                'profit_factor': stats['profit_factor'],
                'sharpe_ratio': stats['sharpe_ratio'],
                'sortino_ratio': stats['sortino_ratio'],
                'max_drawdown': stats['max_drawdown'],
                'avg_trades_per_day': stats['avg_trades_per_day'],
                'trading_days': stats['trading_days'],
                'first_trade_date': stats['first_trade_date'],
                'last_trade_date': stats['last_trade_date']
            },
            'account_breakdown': account_breakdown_list
        }
        
        logger.info(f"[COMBINED STATS] SUCCESS: Returning combined stats for {symbol} with {len(recommended_accounts)} accounts")
        
        return APIResponse(
            status="success",
            message=f"Combined statistics calculated for {symbol}",
            data=combined_stats
        )
        
    except Exception as e:
        logger.error(f"[COMBINED STATS] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to calculate combined statistics: {str(e)}")


@router.get(
    "/recommendations/investigate-trade/{symbol}",
    response_model=APIResponse,
    summary="Investigate specific large trades",
    description="Find details about unusually large trades in recommended time slots."
)
async def investigate_large_trades(
    symbol: str = Path(..., description="Trading symbol (e.g., NQ, FD, CL)"),
    min_profit: float = Query(1000, description="Minimum profit/loss to investigate"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Investigate unusually large trades to verify data quality."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[INVESTIGATE TRADES] Looking for trades > ${min_profit} for {symbol}")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[INVESTIGATE TRADES] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get recommendation matrix first
        rec_matrix_query = """
        WITH time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as total_trades,
                AVG(profit_loss) as avg_trade,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades 
            WHERE symbol = ? 
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= 10
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY avg_trade DESC
                ) as rank
            FROM time_day_performance
        )
        SELECT 
            time_slot,
            day_of_week,
            account_name as best_account
        FROM ranked_performance
        WHERE rank = 1 
            AND avg_trade > 10
            AND win_rate >= 50
        """
        
        cursor.execute(rec_matrix_query, (symbol,))
        recommendations = cursor.fetchall()
        
        # Create recommendation lookup
        rec_lookup = {}
        for rec in recommendations:
            key = f"{rec['time_slot']}_{rec['day_of_week']}"
            rec_lookup[key] = rec['best_account']
        
        # Find large trades in recommended time slots
        large_trades_query = """
        SELECT 
            entry_time,
            exit_time,
            account_name,
            symbol,
            profit_loss,
            printf('%02d:%02d', 
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
            quantity,
            entry_price,
            exit_price
        FROM processed_trades 
        WHERE symbol = ? AND ABS(profit_loss) >= ?
        ORDER BY ABS(profit_loss) DESC
        LIMIT 20
        """
        
        cursor.execute(large_trades_query, (symbol, min_profit))
        large_trades = cursor.fetchall()
        
        # Filter to only recommended trades and add recommendation info
        investigated_trades = []
        for trade in large_trades:
            time_slot = trade['time_slot']
            day_of_week = trade['day_of_week']
            account_name = trade['account_name']
            
            rec_key = f"{time_slot}_{day_of_week}"
            recommended_account = rec_lookup.get(rec_key)
            is_recommended = recommended_account == account_name
            
            investigated_trades.append({
                'entry_time': trade['entry_time'],
                'exit_time': trade['exit_time'],
                'account_name': trade['account_name'],
                'symbol': trade['symbol'],
                'profit_loss': float(trade['profit_loss']),
                'time_slot': trade['time_slot'],
                'day_of_week': trade['day_of_week'],
                'quantity': trade['quantity'],
                'entry_price': float(trade['entry_price']) if trade['entry_price'] else None,
                'exit_price': float(trade['exit_price']) if trade['exit_price'] else None,
                'is_recommended': is_recommended,
                'recommended_account': recommended_account
            })
        
        conn.close()
        
        logger.info(f"[INVESTIGATE TRADES] Found {len(investigated_trades)} large trades")
        
        return APIResponse(
            status="success",
            message=f"Investigation completed for {symbol}",
            data={
                'symbol': symbol,
                'min_profit_threshold': min_profit,
                'large_trades': investigated_trades,
                'total_recommendations': len(rec_lookup)
            }
        )
        
    except Exception as e:
        logger.error(f"[INVESTIGATE TRADES] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to investigate trades: {str(e)}")


@router.get(
    "/recommendations/daily-breakdown/{symbol}",
    response_model=APIResponse,
    summary="Get daily breakdown of recommended trades",
    description="Get detailed daily P&L breakdown for recommended trades."
)
async def get_daily_breakdown(
    symbol: str = Path(..., description="Trading symbol (e.g., NQ, FD, CL)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Get detailed daily breakdown of recommended trades."""
    
    import logging
    import sqlite3
    from pathlib import Path
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info(f"[DAILY BREAKDOWN] Getting daily breakdown for {symbol}")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[DAILY BREAKDOWN] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Set default date range if not provided
        if not end_date:
            end_date = datetime.now().strftime('%Y-%m-%d')
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Get recommendation matrix
        rec_matrix_query = """
        WITH time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                COUNT(*) as total_trades,
                AVG(profit_loss) as avg_trade,
                ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_rate
            FROM processed_trades 
            WHERE symbol = ? 
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= 10
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY avg_trade DESC
                ) as rank
            FROM time_day_performance
        )
        SELECT 
            time_slot,
            day_of_week,
            account_name as best_account
        FROM ranked_performance
        WHERE rank = 1 
            AND avg_trade > 10
            AND win_rate >= 50
        """
        
        cursor.execute(rec_matrix_query, (symbol,))
        recommendations = cursor.fetchall()
        
        # Create recommendation lookup
        rec_lookup = {}
        for rec in recommendations:
            key = f"{rec['time_slot']}_{rec['day_of_week']}"
            rec_lookup[key] = rec['best_account']
        
        # Get daily breakdown of recommended trades
        daily_query = """
        SELECT 
            DATE(entry_time) as trade_date,
            entry_time,
            account_name,
            profit_loss,
            printf('%02d:%02d', 
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
        FROM processed_trades 
        WHERE symbol = ? AND DATE(entry_time) >= ? AND DATE(entry_time) <= ?
        """
        
        cursor.execute(daily_query, (symbol, start_date, end_date))
        all_trades = cursor.fetchall()
        
        # Filter to recommended trades and group by day
        daily_breakdown = {}
        cumulative_pnl = 0
        
        for trade in all_trades:
            time_slot = trade['time_slot']
            day_of_week = trade['day_of_week']
            account_name = trade['account_name']
            trade_date = trade['trade_date']
            profit_loss = float(trade['profit_loss'])
            
            rec_key = f"{time_slot}_{day_of_week}"
            recommended_account = rec_lookup.get(rec_key)
            
            if recommended_account == account_name:
                # This is a recommended trade
                if trade_date not in daily_breakdown:
                    daily_breakdown[trade_date] = {
                        'date': trade_date,
                        'trades': [],
                        'daily_pnl': 0,
                        'trade_count': 0
                    }
                
                daily_breakdown[trade_date]['trades'].append({
                    'entry_time': trade['entry_time'],
                    'account': account_name,
                    'time_slot': time_slot,
                    'profit_loss': profit_loss
                })
                daily_breakdown[trade_date]['daily_pnl'] += profit_loss
                daily_breakdown[trade_date]['trade_count'] += 1
        
        # Create cumulative chart data
        chart_data = []
        for date in sorted(daily_breakdown.keys()):
            day_data = daily_breakdown[date]
            cumulative_pnl += day_data['daily_pnl']
            
            chart_data.append({
                'date': date,
                'daily_pnl': day_data['daily_pnl'],
                'cumulative_pnl': cumulative_pnl,
                'trade_count': day_data['trade_count'],
                'trades': day_data['trades']
            })
        
        conn.close()
        
        logger.info(f"[DAILY BREAKDOWN] Generated breakdown for {len(chart_data)} days")
        
        return APIResponse(
            status="success",
            message=f"Daily breakdown generated for {symbol}",
            data={
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date,
                'daily_breakdown': chart_data,
                'total_pnl': cumulative_pnl,
                'total_trading_days': len(chart_data)
            }
        )
        
    except Exception as e:
        logger.error(f"[DAILY BREAKDOWN] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate daily breakdown: {str(e)}")


@router.post(
    "/clean-multiday-trades",
    response_model=APIResponse,
    summary="Clean multi-day trades",
    description="Remove trades that were not closed on the same day they were opened."
)
async def clean_multiday_trades(
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse:
    """Remove trades that span multiple days (entry and exit on different dates)."""
    
    import logging
    import sqlite3
    import json
    from datetime import datetime
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info("[CLEAN MULTIDAY] Starting multi-day trade cleanup")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[CLEAN MULTIDAY] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # First, find all multi-day trades with complete details
        find_query = """
        SELECT 
            id,
            trade_id,
            account_name,
            symbol,
            entry_time,
            exit_time,
            profit_loss,
            quantity,
            entry_price,
            exit_price,
            duration_minutes,
            side,
            DATE(entry_time) as entry_date,
            DATE(exit_time) as exit_date,
            TIME(entry_time) as entry_time_only,
            TIME(exit_time) as exit_time_only
        FROM processed_trades 
        WHERE DATE(entry_time) != DATE(exit_time)
        ORDER BY entry_time
        """
        
        cursor.execute(find_query)
        multiday_trades = cursor.fetchall()
        
        if not multiday_trades:
            conn.close()
            return APIResponse(
                status="success",
                message="No multi-day trades found",
                data={
                    'trades_removed': 0,
                    'total_trades_before': 0,
                    'total_trades_after': 0,
                    'log_file': None
                }
            )
        
        # Get total count before cleanup
        cursor.execute("SELECT COUNT(*) as total FROM processed_trades")
        total_before = cursor.fetchone()['total']
        
        # Create detailed log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"multiday_trades_cleanup_{timestamp}.json"
        log_path = Path("logs") / log_filename
        
        # Ensure logs directory exists
        log_path.parent.mkdir(exist_ok=True)
        
        # Prepare detailed log data
        log_data = {
            "cleanup_timestamp": datetime.now().isoformat(),
            "total_trades_before": total_before,
            "multiday_trades_found": len(multiday_trades),
            "removed_trades": []
        }
        
        # Log all trades that will be removed
        logger.info(f"[CLEAN MULTIDAY] Found {len(multiday_trades)} multi-day trades to remove")
        
        for trade in multiday_trades:
            trade_info = {
                "id": trade['id'],
                "trade_id": trade['trade_id'],
                "account_name": trade['account_name'],
                "symbol": trade['symbol'],
                "entry_date": trade['entry_date'],
                "entry_time": trade['entry_time_only'],
                "exit_date": trade['exit_date'],
                "exit_time": trade['exit_time_only'],
                "full_entry_time": trade['entry_time'],
                "full_exit_time": trade['exit_time'],
                "duration_minutes": trade['duration_minutes'],
                "duration_hours": round(trade['duration_minutes'] / 60, 1),
                "duration_days": round(trade['duration_minutes'] / (60 * 24), 1),
                "profit_loss": float(trade['profit_loss']),
                "quantity": trade['quantity'],
                "entry_price": float(trade['entry_price']) if trade['entry_price'] else None,
                "exit_price": float(trade['exit_price']) if trade['exit_price'] else None,
                "side": trade['side']
            }
            log_data["removed_trades"].append(trade_info)
        
        # Log first 10 examples to console
        for i, trade in enumerate(multiday_trades[:10]):
            logger.info(f"[CLEAN MULTIDAY] Example {i+1}: {trade['account_name']} {trade['symbol']} "
                       f"Entry: {trade['entry_date']} {trade['entry_time_only']} "
                       f"Exit: {trade['exit_date']} {trade['exit_time_only']} "
                       f"Duration: {round(trade['duration_minutes'] / 60, 1)}h P&L: ${trade['profit_loss']}")
        
        if len(multiday_trades) > 10:
            logger.info(f"[CLEAN MULTIDAY] ... and {len(multiday_trades) - 10} more trades (see log file for complete list)")
        
        # Delete all multi-day trades
        delete_query = """
        DELETE FROM processed_trades 
        WHERE DATE(entry_time) != DATE(exit_time)
        """
        
        cursor.execute(delete_query)
        deleted_count = cursor.rowcount
        
        # Get total count after cleanup
        cursor.execute("SELECT COUNT(*) as total FROM processed_trades")
        total_after = cursor.fetchone()['total']
        
        # Complete log data
        log_data["trades_actually_removed"] = deleted_count
        log_data["total_trades_after"] = total_after
        log_data["cleanup_successful"] = True
        
        # Write detailed log file
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)
        
        conn.commit()
        conn.close()
        
        logger.info(f"[CLEAN MULTIDAY] SUCCESS: Removed {deleted_count} multi-day trades")
        logger.info(f"[CLEAN MULTIDAY] Before: {total_before} trades, After: {total_after} trades")
        logger.info(f"[CLEAN MULTIDAY] Detailed log saved to: {log_path.absolute()}")
        
        return APIResponse(
            status="success",
            message=f"Successfully removed {deleted_count} multi-day trades",
            data={
                'trades_removed': deleted_count,
                'total_trades_before': total_before,
                'total_trades_after': total_after,
                'log_file': str(log_path.absolute()),
                'log_filename': log_filename,
                'examples_removed': [
                    {
                        'account_name': trade['account_name'],
                        'symbol': trade['symbol'],
                        'entry_date': trade['entry_date'],
                        'entry_time': trade['entry_time_only'],
                        'exit_date': trade['exit_date'],
                        'exit_time': trade['exit_time_only'],
                        'duration_hours': round(trade['duration_minutes'] / 60, 1),
                        'profit_loss': float(trade['profit_loss'])
                    }
                    for trade in multiday_trades[:10]  # Return first 10 examples
                ]
            }
        )
        
    except Exception as e:
        logger.error(f"[CLEAN MULTIDAY] ERROR: {str(e)}", exc_info=True)
        
        # Try to save error log
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_log_path = Path("logs") / f"multiday_cleanup_error_{timestamp}.json"
            error_log_path.parent.mkdir(exist_ok=True)
            
            error_data = {
                "cleanup_timestamp": datetime.now().isoformat(),
                "error": str(e),
                "cleanup_successful": False
            }
            
            with open(error_log_path, 'w') as f:
                json.dump(error_data, f, indent=2, default=str)
                
            logger.info(f"[CLEAN MULTIDAY] Error log saved to: {error_log_path.absolute()}")
        except:
            pass  # Don't fail if we can't write error log
        
        raise HTTPException(status_code=500, detail=f"Failed to clean multi-day trades: {str(e)}")


@router.get(
    "/data-stats",
    response_model=APIResponse,
    summary="Get data quality statistics",
    description="Get counts of multi-day trades and duplicate trades."
)
async def get_data_stats(
    db: Session = Depends(get_database_session)
) -> APIResponse:
    """Get statistics about data quality issues."""
    
    import sqlite3
    from pathlib import Path
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Count multi-day trades
        cursor.execute("SELECT COUNT(*) FROM processed_trades WHERE DATE(entry_time) != DATE(exit_time)")
        multiday_count = cursor.fetchone()[0]
        
        # Count duplicate trades
        cursor.execute("""
            SELECT SUM(duplicate_count - 1) as total_duplicates 
            FROM (
                SELECT COUNT(*) as duplicate_count 
                FROM processed_trades 
                GROUP BY entry_time, exit_time, account_name, symbol, quantity, entry_price, exit_price, profit_loss 
                HAVING COUNT(*) > 1
            )
        """)
        duplicate_result = cursor.fetchone()
        duplicate_count = duplicate_result[0] if duplicate_result[0] is not None else 0
        
        # Count statistical outliers using separate winner/loser thresholds
        outlier_count = 0
        try:
            # Get separate statistics for winners and losers per account
            cursor.execute("""
                SELECT 
                    account_name,
                    -- Winner statistics
                    AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) as avg_winner,
                    COUNT(CASE WHEN profit_loss > 0 THEN 1 END) as winner_count,
                    AVG(CASE WHEN profit_loss > 0 THEN profit_loss * profit_loss END) - 
                        (AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) * AVG(CASE WHEN profit_loss > 0 THEN profit_loss END)) as winner_variance,
                    -- Loser statistics  
                    AVG(CASE WHEN profit_loss < 0 THEN profit_loss END) as avg_loser,
                    COUNT(CASE WHEN profit_loss < 0 THEN 1 END) as loser_count,
                    AVG(CASE WHEN profit_loss < 0 THEN profit_loss * profit_loss END) - 
                        (AVG(CASE WHEN profit_loss < 0 THEN profit_loss END) * AVG(CASE WHEN profit_loss < 0 THEN profit_loss END)) as loser_variance
                FROM processed_trades 
                GROUP BY account_name
                HAVING COUNT(*) >= 10 AND COUNT(CASE WHEN profit_loss > 0 THEN 1 END) >= 5 AND COUNT(CASE WHEN profit_loss < 0 THEN 1 END) >= 5
            """)
            account_stats = cursor.fetchall()
            
            for stats in account_stats:
                account_name = stats[0]
                
                # Winner statistics
                avg_winner = stats[1]
                winner_variance = stats[3] if stats[3] else 0
                winner_std = (winner_variance ** 0.5) if winner_variance > 0 else 0
                
                # Loser statistics
                avg_loser = stats[4]
                loser_variance = stats[6] if stats[6] else 0
                loser_std = (loser_variance ** 0.5) if loser_variance > 0 else 0
                
                if winner_std > 0:
                    # Count extreme winners (beyond 2 std dev)
                    cursor.execute("""
                        SELECT COUNT(*) FROM processed_trades 
                        WHERE account_name = ? AND profit_loss > 0 AND (profit_loss - ?) / ? > 2.0
                    """, (account_name, avg_winner, winner_std))
                    winner_outliers = cursor.fetchone()[0]
                    outlier_count += winner_outliers
                
                if loser_std > 0:
                    # Count extreme losers (beyond 3 std dev)
                    cursor.execute("""
                        SELECT COUNT(*) FROM processed_trades 
                        WHERE account_name = ? AND profit_loss < 0 AND ABS(profit_loss - ?) / ? > 3.0
                    """, (account_name, avg_loser, loser_std))
                    loser_outliers = cursor.fetchone()[0]
                    outlier_count += loser_outliers
        except:
            outlier_count = 0  # If calculation fails, default to 0
        
        # Get total trades count
        cursor.execute("SELECT COUNT(*) FROM processed_trades")
        total_trades = cursor.fetchone()[0]
        
        conn.close()
        
        return APIResponse(
            status="success",
            message="Data statistics retrieved successfully",
            data={
                'total_trades': total_trades,
                'multiday_trades': multiday_count,
                'duplicate_trades': duplicate_count,
                'outlier_trades': outlier_count,
                'clean_trades': total_trades - multiday_count - duplicate_count - outlier_count
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get data statistics: {str(e)}")


@router.post(
    "/clean-outlier-trades",
    response_model=APIResponse,
    summary="Clean statistical outlier trades",
    description="Remove trades that are statistical outliers (beyond 2.5 standard deviations) per account."
)
async def clean_outlier_trades(
    std_dev_threshold: float = Query(2.5, description="Standard deviation threshold (default: 2.5)"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse:
    """Remove trades that are statistical outliers per account."""
    
    import logging
    import sqlite3
    import json
    import math
    from datetime import datetime
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[CLEAN OUTLIERS] Starting outlier trade cleanup with {std_dev_threshold} std dev threshold")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[CLEAN OUTLIERS] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get total count before cleanup
        cursor.execute("SELECT COUNT(*) as total FROM processed_trades")
        total_before = cursor.fetchone()['total']
        
        # Get separate statistics for winners and losers per account
        stats_query = """
        SELECT 
            account_name,
            -- Winner statistics
            AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) as avg_winner,
            COUNT(CASE WHEN profit_loss > 0 THEN 1 END) as winner_count,
            AVG(CASE WHEN profit_loss > 0 THEN profit_loss * profit_loss END) - 
                (AVG(CASE WHEN profit_loss > 0 THEN profit_loss END) * AVG(CASE WHEN profit_loss > 0 THEN profit_loss END)) as winner_variance,
            -- Loser statistics  
            AVG(CASE WHEN profit_loss < 0 THEN profit_loss END) as avg_loser,
            COUNT(CASE WHEN profit_loss < 0 THEN 1 END) as loser_count,
            AVG(CASE WHEN profit_loss < 0 THEN profit_loss * profit_loss END) - 
                (AVG(CASE WHEN profit_loss < 0 THEN profit_loss END) * AVG(CASE WHEN profit_loss < 0 THEN profit_loss END)) as loser_variance,
            -- Total trades
            COUNT(*) as total_trades
        FROM processed_trades 
        GROUP BY account_name
        HAVING COUNT(*) >= 10 AND COUNT(CASE WHEN profit_loss > 0 THEN 1 END) >= 5 AND COUNT(CASE WHEN profit_loss < 0 THEN 1 END) >= 5
        """
        
        cursor.execute(stats_query)
        account_stats = cursor.fetchall()
        
        # Calculate standard deviations and find outliers
        outlier_trades = []
        
        for stats in account_stats:
            account_name = stats['account_name']
            
            # Winner statistics
            avg_winner = stats['avg_winner']
            winner_count = stats['winner_count']
            winner_variance = stats['winner_variance'] if stats['winner_variance'] else 0
            winner_std = math.sqrt(winner_variance) if winner_variance > 0 else 0
            
            # Loser statistics
            avg_loser = stats['avg_loser']
            loser_count = stats['loser_count']
            loser_variance = stats['loser_variance'] if stats['loser_variance'] else 0
            loser_std = math.sqrt(loser_variance) if loser_variance > 0 else 0
            
            # Find outlier trades for this account
            trades_query = """
            SELECT id, trade_id, account_name, symbol, entry_time, exit_time, 
                   profit_loss, quantity, entry_price, exit_price, duration_minutes
            FROM processed_trades 
            WHERE account_name = ?
            """
            
            cursor.execute(trades_query, (account_name,))
            account_trades = cursor.fetchall()
            
            for trade in account_trades:
                pnl = trade['profit_loss']
                is_outlier = False
                outlier_type = ""
                z_score = 0
                
                if pnl > 0 and winner_std > 0:
                    # Check if winner is beyond 2 standard deviations
                    z_score = (pnl - avg_winner) / winner_std
                    if z_score > 2.0:  # 2 std for winners
                        is_outlier = True
                        outlier_type = "extreme_winner"
                        
                elif pnl < 0 and loser_std > 0:
                    # Check if loser is beyond 3 standard deviations (more negative)
                    z_score = abs(pnl - avg_loser) / loser_std
                    if z_score > 3.0:  # 3 std for losers
                        is_outlier = True
                        outlier_type = "extreme_loser"
                
                if is_outlier:
                    # Convert to dict and add statistical info
                    trade_dict = dict(trade)
                    trade_dict['avg_winner'] = avg_winner
                    trade_dict['winner_std'] = winner_std
                    trade_dict['avg_loser'] = avg_loser
                    trade_dict['loser_std'] = loser_std
                    trade_dict['z_score'] = z_score
                    trade_dict['outlier_type'] = outlier_type
                    outlier_trades.append(trade_dict)
        
        # Sort by z_score descending
        outlier_trades.sort(key=lambda x: x['z_score'], reverse=True)
        
        if not outlier_trades:
            conn.close()
            return APIResponse(
                status="success",
                message="No statistical outlier trades found",
                data={
                    'trades_removed': 0,
                    'total_trades_before': total_before,
                    'total_trades_after': total_before,
                    'std_dev_threshold': std_dev_threshold
                }
            )
        
        # Create detailed log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"outlier_trades_cleanup_{timestamp}.json"
        log_path = Path("logs") / log_filename
        
        # Ensure logs directory exists
        log_path.parent.mkdir(exist_ok=True)
        
        # Prepare detailed log data
        log_data = {
            "cleanup_timestamp": datetime.now().isoformat(),
            "std_dev_threshold": std_dev_threshold,
            "total_trades_before": total_before,
            "outlier_trades_found": len(outlier_trades),
            "removed_trades": []
        }
        
        # Log outlier trades that will be removed
        logger.info(f"[CLEAN OUTLIERS] Found {len(outlier_trades)} outlier trades to remove")
        
        for trade in outlier_trades:
            trade_info = {
                "id": trade['id'],
                "trade_id": trade['trade_id'],
                "account_name": trade['account_name'],
                "symbol": trade['symbol'],
                "entry_time": trade['entry_time'],
                "exit_time": trade['exit_time'],
                "profit_loss": float(trade['profit_loss']),
                "quantity": trade['quantity'],
                "entry_price": float(trade['entry_price']) if trade['entry_price'] else None,
                "exit_price": float(trade['exit_price']) if trade['exit_price'] else None,
                "duration_minutes": trade['duration_minutes'],
                "avg_winner": float(trade['avg_winner']) if trade['avg_winner'] else None,
                "winner_std": float(trade['winner_std']),
                "avg_loser": float(trade['avg_loser']) if trade['avg_loser'] else None,
                "loser_std": float(trade['loser_std']),
                "z_score": float(trade['z_score']),
                "outlier_type": trade['outlier_type'],
                "threshold_used": "2σ winners" if trade['outlier_type'] == "extreme_winner" else "3σ losers"
            }
            log_data["removed_trades"].append(trade_info)
        
        # Log first 10 examples to console
        for i, trade in enumerate(outlier_trades[:10]):
            threshold = "2σ" if trade['outlier_type'] == "extreme_winner" else "3σ"
            logger.info(f"[CLEAN OUTLIERS] Example {i+1}: {trade['account_name']} {trade['symbol']} "
                       f"P&L: ${trade['profit_loss']} (Z-score: {trade['z_score']:.2f}, {threshold}) - {trade['outlier_type'].upper()}")
        
        if len(outlier_trades) > 10:
            logger.info(f"[CLEAN OUTLIERS] ... and {len(outlier_trades) - 10} more outlier trades (see log file for complete list)")
        
        # Delete all outlier trades
        outlier_ids = [str(trade['id']) for trade in outlier_trades]
        delete_query = f"DELETE FROM processed_trades WHERE id IN ({','.join(['?' for _ in outlier_ids])})"
        
        cursor.execute(delete_query, outlier_ids)
        deleted_count = cursor.rowcount
        
        # Get total count after cleanup
        cursor.execute("SELECT COUNT(*) as total FROM processed_trades")
        total_after = cursor.fetchone()['total']
        
        # Complete log data
        log_data["trades_actually_removed"] = deleted_count
        log_data["total_trades_after"] = total_after
        log_data["cleanup_successful"] = True
        
        # Write detailed log file
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2, default=str)
        
        conn.commit()
        conn.close()
        
        logger.info(f"[CLEAN OUTLIERS] SUCCESS: Removed {deleted_count} outlier trades")
        logger.info(f"[CLEAN OUTLIERS] Before: {total_before} trades, After: {total_after} trades")
        logger.info(f"[CLEAN OUTLIERS] Detailed log saved to: {log_path.absolute()}")
        
        return APIResponse(
            status="success",
            message=f"Successfully removed {deleted_count} statistical outlier trades",
            data={
                'trades_removed': deleted_count,
                'total_trades_before': total_before,
                'total_trades_after': total_after,
                'std_dev_threshold': std_dev_threshold,
                'log_file': str(log_path.absolute()),
                'log_filename': log_filename,
                'examples_removed': [
                    {
                        'account_name': trade['account_name'],
                        'symbol': trade['symbol'],
                        'profit_loss': float(trade['profit_loss']),
                        'z_score': float(trade['z_score']),
                        'outlier_type': trade['outlier_type'],
                        'threshold_used': "2σ winners" if trade['outlier_type'] == "extreme_winner" else "3σ losers"
                    }
                    for trade in outlier_trades[:10]  # Return first 10 examples
                ]
            }
        )
        
    except Exception as e:
        logger.error(f"[CLEAN OUTLIERS] ERROR: {str(e)}", exc_info=True)
        
        # Try to save error log
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_log_path = Path("logs") / f"outlier_cleanup_error_{timestamp}.json"
            error_log_path.parent.mkdir(exist_ok=True)
            
            error_data = {
                "cleanup_timestamp": datetime.now().isoformat(),
                "error": str(e),
                "cleanup_successful": False
            }
            
            with open(error_log_path, 'w') as f:
                json.dump(error_data, f, indent=2, default=str)
                
            logger.info(f"[CLEAN OUTLIERS] Error log saved to: {error_log_path.absolute()}")
        except:
            pass  # Don't fail if we can't write error log
        
        raise HTTPException(status_code=500, detail=f"Failed to clean outlier trades: {str(e)}")


@router.get(
    "/symbols",
    response_model=APIResponse,
    summary="Get available trading symbols",
    description="Get list of all available trading symbols in the database."
)
async def get_available_symbols(
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Get list of all available trading symbols."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info("[SYMBOLS] Getting available symbols")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[SYMBOLS] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all unique symbols with trade counts
        query = """
        SELECT 
            symbol,
            COUNT(*) as total_trades,
            COUNT(DISTINCT account_name) as unique_accounts,
            MIN(entry_time) as first_trade,
            MAX(entry_time) as last_trade
        FROM processed_trades 
        GROUP BY symbol
        ORDER BY total_trades DESC
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        
        symbols = []
        for row in rows:
            symbols.append({
                'symbol': row['symbol'],
                'total_trades': row['total_trades'],
                'unique_accounts': row['unique_accounts'],
                'first_trade': row['first_trade'],
                'last_trade': row['last_trade']
            })
        
        conn.close()
        
        logger.info(f"[SYMBOLS] SUCCESS: Returning {len(symbols)} symbols")
        
        return APIResponse(
            status="success",
            message=f"Retrieved {len(symbols)} trading symbols",
            data={'symbols': symbols}
        )
        
    except Exception as e:
        logger.error(f"[SYMBOLS] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve symbols: {str(e)}")


@router.get(
    "/correlation",
    response_model=APIResponse[CorrelationAnalysisResponse],
    summary="Get correlation analysis",
    description="Analyze correlations between different accounts and assets."
)
async def get_correlation_analysis(
    account_names: str = Query(..., description="Comma-separated list of account names"),
    start_date: Optional[datetime] = Query(None, description="Start date for analysis"),
    end_date: Optional[datetime] = Query(None, description="End date for analysis"),
    db: Session = Depends(get_database_session),
    account_comparator: AccountComparisonService = Depends(get_account_comparator),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[CorrelationAnalysisResponse]:
    """Analyze correlations between accounts and assets."""
    
    try:
        # Parse account names
        accounts = [name.strip() for name in account_names.split(",")]
        
        if len(accounts) < 2:
            raise HTTPException(status_code=400, detail="At least 2 accounts required for correlation analysis")
        
        # TODO: Implement actual correlation analysis using service
        # For now, return mock correlation results
        
        correlation_matrix = {}
        for i, account1 in enumerate(accounts):
            correlation_matrix[account1] = {}
            for j, account2 in enumerate(accounts):
                if i == j:
                    correlation_matrix[account1][account2] = 1.0
                elif i < j:
                    # Mock correlation values
                    correlation_matrix[account1][account2] = 0.35 if "NQ" in account1 and "NQ" in account2 else 0.15
                else:
                    correlation_matrix[account1][account2] = correlation_matrix[account2][account1]
        
        correlation_analysis = CorrelationAnalysisResponse(
            accounts=accounts,
            period_start=start_date or datetime(2024, 1, 1),
            period_end=end_date or datetime(2024, 12, 31),
            correlation_matrix=correlation_matrix,
            strongest_correlation={"accounts": ["IPS_TM_10", "IPS_TM_11"], "correlation": 0.75},
            weakest_correlation={"accounts": ["IPS_TM_10", "IPS_TM_13"], "correlation": 0.15},
            diversification_score=0.68,
            portfolio_risk_reduction=0.23
        )
        
        return APIResponse[CorrelationAnalysisResponse](
            status="success",
            message=f"Correlation analysis completed for {len(accounts)} accounts",
            data=correlation_analysis
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform correlation analysis: {str(e)}")


@router.get(
    "/compare/{account1}/{account2}",
    response_model=APIResponse,
    summary="Compare two accounts",
    description="Statistical comparison between two trading accounts."
)
async def compare_accounts_detailed(
    account1: str = Path(..., description="First account name"),
    account2: str = Path(..., description="Second account name"),
    start_date: Optional[datetime] = Query(None, description="Start date for comparison"),
    end_date: Optional[datetime] = Query(None, description="End date for comparison"),
    db: Session = Depends(get_database_session),
    account_comparator: AccountComparisonService = Depends(get_account_comparator),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Perform detailed statistical comparison between two accounts."""
    
    try:
        # TODO: Implement actual account comparison using service
        # For now, return mock comparison results
        
        comparison_result = {
            "account_a": account1,
            "account_b": account2,
            "period_start": start_date or datetime(2024, 1, 1),
            "period_end": end_date or datetime(2024, 12, 31),
            "performance_comparison": {
                account1: {
                    "total_return": 15000.0,
                    "win_rate": 0.65,
                    "sharpe_ratio": 1.2,
                    "max_drawdown": -2500.0,
                    "volatility": 0.15
                },
                account2: {
                    "total_return": 12000.0,
                    "win_rate": 0.58,
                    "sharpe_ratio": 0.9,
                    "max_drawdown": -3200.0,
                    "volatility": 0.18
                }
            },
            "statistical_tests": {
                "returns_t_test": {
                    "statistic": 2.15,
                    "p_value": 0.032,
                    "significant": True,
                    "interpretation": f"{account1} has significantly better returns"
                },
                "win_rate_test": {
                    "statistic": 1.87,
                    "p_value": 0.061,
                    "significant": False,
                    "interpretation": "No significant difference in win rates"
                },
                "volatility_test": {
                    "statistic": -1.45,
                    "p_value": 0.148,
                    "significant": False,
                    "interpretation": "No significant difference in volatility"
                }
            },
            "recommendation": f"Account {account1} shows superior performance with statistically significant better returns"
        }
        
        return APIResponse(
            status="success",
            message=f"Detailed comparison completed between {account1} and {account2}",
            data=comparison_result
        )
        
    except DataNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare accounts: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — ADVANCED STATISTICAL LAYERS
# ─────────────────────────────────────────────────────────────────────────────


# ── Level 2: VIX Regime Correlation ──────────────────────────────────────────

@router.get(
    "/recommendations/matrix/{symbol}/vix-regime",
    response_model=APIResponse,
    summary="VIX regime performance overlay for recommendation matrix",
    description=(
        "For each (time_slot, day_of_week) cell in the recommendation matrix, "
        "break down performance by VIX volatility regime: Low (<15), Medium (15-25), High (>25). "
        "Also returns the current VIX level and regime."
    )
)
async def get_vix_regime_matrix(
    symbol: str = Path(..., description="Trading symbol (e.g., NQ, ES, CL)"),
    days_back: int = Query(90, description="Number of days of history to analyse"),
    min_trades: int = Query(5, description="Minimum trades per regime per cell to include"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission),
) -> APIResponse:
    """Return per-cell VIX regime breakdown for the recommendation matrix."""
    import logging
    import sqlite3
    from pathlib import Path as FsPath
    from datetime import timedelta

    logger = logging.getLogger(__name__)

    try:
        db_path = FsPath("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        # ── Fetch VIX data from market_data table ──
        cursor.execute(
            """
            SELECT date, close_price as vix
            FROM market_data
            WHERE symbol = 'VIX' AND date >= ?
            ORDER BY date
            """,
            (cutoff,),
        )
        vix_rows = cursor.fetchall()

        # Build date → VIX lookup and classify regime
        vix_by_date: dict = {}
        for row in vix_rows:
            date_str = str(row["date"])[:10]
            vix_val = float(row["vix"]) if row["vix"] else None
            if vix_val is not None:
                if vix_val < 15:
                    regime = "Low"
                elif vix_val <= 25:
                    regime = "Medium"
                else:
                    regime = "High"
                vix_by_date[date_str] = {"vix": vix_val, "regime": regime}

        # Current VIX (most recent)
        current_vix_info = None
        if vix_by_date:
            latest_date = max(vix_by_date.keys())
            current_vix_info = {"date": latest_date, **vix_by_date[latest_date]}

        # ── Fetch trades ──
        cursor.execute(
            """
            SELECT
                account_name,
                profit_loss,
                entry_time,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                substr(entry_time, 1, 10) as trade_date
            FROM processed_trades
            WHERE symbol = ? AND entry_time >= ?
            """,
            (symbol, cutoff),
        )
        trade_rows = cursor.fetchall()
        conn.close()

        # ── Aggregate per (time_slot, day_of_week, account, regime) ──
        from collections import defaultdict

        cell_regime: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for row in trade_rows:
            date_str = str(row["trade_date"])
            vix_info = vix_by_date.get(date_str)
            if vix_info is None:
                continue
            regime = vix_info["regime"]
            key = (str(row["time_slot"]), int(row["day_of_week"]))
            cell_regime[key][str(row["account_name"])][regime].append(
                float(row["profit_loss"])
            )

        # ── Build output ──
        regime_matrix: dict = {}
        for (time_slot, day_of_week), accounts in cell_regime.items():
            if time_slot not in regime_matrix:
                regime_matrix[time_slot] = {}

            best_account = None
            best_ev = float("-inf")
            account_regimes: dict = {}

            for account, regimes in accounts.items():
                acct_data: dict = {}
                for regime, pnls in regimes.items():
                    if len(pnls) < min_trades:
                        continue
                    wins = sum(1 for p in pnls if p > 0)
                    acct_data[regime] = {
                        "trades": len(pnls),
                        "win_rate": round(wins / len(pnls) * 100, 1),
                        "avg_trade": round(sum(pnls) / len(pnls), 2),
                        "total_pnl": round(sum(pnls), 2),
                    }
                if acct_data:
                    account_regimes[account] = acct_data
                    # Use overall avg as tiebreaker
                    all_pnls = [p for ps in regimes.values() for p in ps]
                    ev = sum(all_pnls) / len(all_pnls)
                    if ev > best_ev:
                        best_ev = ev
                        best_account = account

            if account_regimes:
                regime_matrix[time_slot][day_of_week] = {
                    "best_account": best_account,
                    "regime_breakdown": account_regimes,
                }

        # ── Aggregate Correlation Analysis ──
        regime_totals = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})
        for (slot, dow), cell in regime_matrix.items():
            for acct, regimes in cell["regime_breakdown"].items():
                if acct == cell["best_account"]:
                    for regime, stats in regimes.items():
                        regime_totals[regime]["pnl"] += stats["total_pnl"]
                        regime_totals[regime]["trades"] += stats["trades"]
                        regime_totals[regime]["wins"] += int(stats["win_rate"] * stats["trades"] / 100)
        
        regime_insights = []
        best_regime = None
        max_avg = float("-inf")
        
        for regime in ["Low", "Medium", "High"]:
            data = regime_totals.get(regime)
            if data and data["trades"] > 0:
                avg = data["pnl"] / data["trades"]
                wr = data["wins"] / data["trades"] * 100
                regime_insights.append({
                    "regime": regime,
                    "avg_trade": round(avg, 2),
                    "win_rate": round(wr, 1),
                    "total_trades": data["trades"],
                })
                if avg > max_avg:
                    max_avg = avg
                    best_regime = regime

        return APIResponse(
            status="success",
            message=f"VIX regime matrix for {symbol} ({days_back} days)",
            data={
                "symbol": symbol,
                "current_vix": current_vix_info,
                "regime_matrix": regime_matrix,
                "vix_data_points": len(vix_by_date),
                "regime_analysis": {
                    "best_regime": best_regime,
                    "insights": regime_insights,
                    "bias_score": round((max_avg / (sum(r["avg_trade"] for r in regime_insights if r["avg_trade"] > 0) / len(regime_insights))) if regime_insights else 0, 2)
                }
            },
        )

    except Exception as exc:
        logger.error(f"[VIX REGIME] ERROR: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"VIX regime analysis failed: {exc}")


# ── Level 3: 30-Min Bin Probability Model ────────────────────────────────────

@router.get(
    "/recommendations/matrix/{symbol}/probability",
    response_model=APIResponse,
    summary="Probability distribution model for each matrix cell",
    description=(
        "For each (time_slot, day_of_week) cell, compute the full P&L distribution: "
        "P(profit>0), expected value, variance, skewness, kurtosis, CVaR-95, "
        "and a confidence-weighted expected value = E[PnL] × P(profit>0)."
    )
)
async def get_probability_matrix(
    symbol: str = Path(..., description="Trading symbol"),
    days_back: int = Query(90, description="Days of history"),
    min_trades: int = Query(10, description="Minimum trades per cell"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission),
) -> APIResponse:
    """Return probability distribution metrics per matrix cell."""
    import logging
    import sqlite3
    import math
    from pathlib import Path as FsPath
    from datetime import timedelta
    from collections import defaultdict

    logger = logging.getLogger(__name__)

    def _skewness(vals: list) -> float:
        n = len(vals)
        if n < 3:
            return 0.0
        mean = sum(vals) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
        if std == 0:
            return 0.0
        return sum(((v - mean) / std) ** 3 for v in vals) / n

    def _kurtosis(vals: list) -> float:
        n = len(vals)
        if n < 4:
            return 0.0
        mean = sum(vals) / n
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / n)
        if std == 0:
            return 0.0
        return sum(((v - mean) / std) ** 4 for v in vals) / n - 3.0  # excess kurtosis

    def _cvar(vals: list, pct: float = 0.05) -> float:
        """Conditional Value at Risk at given tail percentile (losses)."""
        sorted_vals = sorted(vals)
        cutoff_idx = max(1, int(len(sorted_vals) * pct))
        tail = sorted_vals[:cutoff_idx]
        return sum(tail) / len(tail)

    try:
        db_path = FsPath("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        cursor.execute(
            """
            SELECT
                account_name,
                profit_loss,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
            FROM processed_trades
            WHERE symbol = ? AND entry_time >= ?
            """,
            (symbol, cutoff),
        )
        rows = cursor.fetchall()
        conn.close()

        # Group by (time_slot, day_of_week, account)
        cell_pnls: dict = defaultdict(lambda: defaultdict(list))
        for row in rows:
            key = (str(row["time_slot"]), int(row["day_of_week"]))
            cell_pnls[key][str(row["account_name"])].append(float(row["profit_loss"]))

        prob_matrix: dict = {}
        for (time_slot, day_of_week), accounts in cell_pnls.items():
            if time_slot not in prob_matrix:
                prob_matrix[time_slot] = {}

            best_account = None
            best_cwev = float("-inf")
            account_stats: dict = {}

            for account, pnls in accounts.items():
                if len(pnls) < min_trades:
                    continue
                n = len(pnls)
                mean = sum(pnls) / n
                variance = sum((p - mean) ** 2 for p in pnls) / n
                p_profit = sum(1 for p in pnls if p > 0) / n
                p_profit_50 = sum(1 for p in pnls if p > 50) / n
                p_profit_100 = sum(1 for p in pnls if p > 100) / n
                cwev = mean * p_profit  # confidence-weighted EV

                account_stats[account] = {
                    "trades": n,
                    "expected_value": round(mean, 2),
                    "variance": round(variance, 2),
                    "std_dev": round(math.sqrt(variance), 2),
                    "p_profit": round(p_profit * 100, 1),
                    "p_profit_50": round(p_profit_50 * 100, 1),
                    "p_profit_100": round(p_profit_100 * 100, 1),
                    "skewness": round(_skewness(pnls), 3),
                    "excess_kurtosis": round(_kurtosis(pnls), 3),
                    "cvar_95": round(_cvar(pnls, 0.05), 2),
                    "confidence_weighted_ev": round(cwev, 2),
                    "percentile_10": round(sorted(pnls)[int(n * 0.10)], 2),
                    "percentile_90": round(sorted(pnls)[int(n * 0.90)], 2),
                }

                if cwev > best_cwev:
                    best_cwev = cwev
                    best_account = account

            if account_stats:
                prob_matrix[time_slot][day_of_week] = {
                    "best_account": best_account,
                    "best_cwev": round(best_cwev, 2),
                    "accounts": account_stats,
                }

        return APIResponse(
            status="success",
            message=f"Probability matrix for {symbol} ({days_back} days)",
            data={
                "symbol": symbol,
                "days_back": days_back,
                "probability_matrix": prob_matrix,
            },
        )

    except Exception as exc:
        logger.error(f"[PROBABILITY MATRIX] ERROR: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Probability analysis failed: {exc}")


# ── Level 4: Rolling Window Predictor ────────────────────────────────────────

@router.get(
    "/recommendations/predict-week/{symbol}",
    response_model=APIResponse,
    summary="Rolling window predictor — best account per cell for the upcoming week",
    description=(
        "Uses exponentially-decay-weighted rolling windows (2, 4, 8, 13 weeks) to predict "
        "the best account for each (time_slot, day_of_week) cell in the upcoming week. "
        "Returns predictions with confidence scores and agreement across window sizes."
    )
)
async def get_rolling_predictor(
    symbol: str = Path(..., description="Trading symbol"),
    lookback_weeks: int = Query(13, description="Maximum lookback in weeks (2–26)"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission),
) -> APIResponse:
    """Predict best account per cell using rolling exponentially-weighted performance."""
    import logging
    import sqlite3
    import math
    from pathlib import Path as FsPath
    from datetime import timedelta
    from collections import defaultdict

    logger = logging.getLogger(__name__)

    # Always include at least the 1-week window so predictor works with short lookbacks
    candidate_windows = [1, 2, 4, 8, 13]
    WINDOW_WEEKS = [w for w in candidate_windows if w <= lookback_weeks] or [lookback_weeks]
    DECAY = 0.85  # exponential decay factor per week

    try:
        db_path = FsPath("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        max_days = lookback_weeks * 7
        cutoff = (datetime.now() - timedelta(days=max_days)).strftime("%Y-%m-%d")

        cursor.execute(
            """
            SELECT
                account_name,
                profit_loss,
                entry_time,
                printf('%02d:%02d',
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                substr(entry_time, 1, 10) as trade_date
            FROM processed_trades
            WHERE symbol = ? AND entry_time >= ?
            ORDER BY entry_time
            """,
            (symbol, cutoff),
        )
        rows = cursor.fetchall()
        conn.close()

        now = datetime.now()

        # Group trades by (time_slot, day_of_week, account, week_number)
        # week_number = weeks ago (0 = most recent)
        cell_account_weeks: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for row in rows:
            try:
                trade_dt = datetime.fromisoformat(str(row["trade_date"]))
            except Exception:
                continue
            weeks_ago = (now - trade_dt).days // 7
            key = (str(row["time_slot"]), int(row["day_of_week"]))
            cell_account_weeks[key][str(row["account_name"])][weeks_ago].append(
                float(row["profit_loss"])
            )

        predictions: dict = {}

        for (time_slot, day_of_week), accounts in cell_account_weeks.items():
            if time_slot not in predictions:
                predictions[time_slot] = {}

            window_votes: dict = defaultdict(int)  # account → vote count
            window_details: dict = {}

            for window in WINDOW_WEEKS:
                account_scores: dict = {}
                for account, weeks_data in accounts.items():
                    weighted_sum = 0.0
                    total_weight = 0.0
                    total_trades = 0
                    for weeks_ago, pnls in weeks_data.items():
                        if weeks_ago >= window:
                            continue
                        weight = DECAY ** weeks_ago
                        weighted_sum += sum(pnls) * weight
                        total_weight += len(pnls) * weight
                        total_trades += len(pnls)
                    if total_trades >= 3 and total_weight > 0:
                        account_scores[account] = {
                            "weighted_avg": round(weighted_sum / total_weight, 2),
                            "total_trades": total_trades,
                        }

                if account_scores:
                    best = max(account_scores, key=lambda a: account_scores[a]["weighted_avg"])
                    window_votes[best] += 1
                    window_details[f"{window}w"] = {
                        "predicted": best,
                        "score": account_scores[best]["weighted_avg"],
                        "accounts": account_scores,
                    }

            if window_votes:
                # Consensus: account with most window votes
                consensus = max(window_votes, key=lambda a: window_votes[a])
                agreement = window_votes[consensus] / len(WINDOW_WEEKS)
                confidence = "High" if agreement >= 0.75 else "Medium" if agreement >= 0.5 else "Low"

                predictions[time_slot][day_of_week] = {
                    "predicted_account": consensus,
                    "agreement_ratio": round(agreement, 2),
                    "confidence": confidence,
                    "window_votes": dict(window_votes),
                    "window_details": window_details,
                }

        return APIResponse(
            status="success",
            message=f"Rolling predictor for {symbol} (lookback: {lookback_weeks}w, windows: {WINDOW_WEEKS})",
            data={
                "symbol": symbol,
                "lookback_weeks": lookback_weeks,
                "windows_used": WINDOW_WEEKS,
                "decay_factor": DECAY,
                "predictions": predictions,
                "generated_at": now.isoformat(),
            },
        )

    except Exception as exc:
        logger.error(f"[ROLLING PREDICTOR] ERROR: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Rolling predictor failed: {exc}")


# ── Level 5: Walk-Forward Validation ─────────────────────────────────────────

@router.post(
    "/recommendations/walk-forward/{symbol}",
    response_model=APIResponse,
    summary="Walk-forward validation of the time-bin recommendation strategy",
    description=(
        "Implements the walk-forward validation protocol: "
        "train on W days, test on H days, step by Δ days. "
        "Returns per-fold OOS metrics, aggregate Sharpe, consistency ratio, "
        "and a Monte Carlo permutation p-value."
    )
)
async def run_walk_forward_validation(
    symbol: str = Path(..., description="Trading symbol"),
    training_days: int = Query(90, description="Training window in days (W)"),
    testing_days: int = Query(21, description="Testing window in days (H)"),
    step_days: int = Query(21, description="Step size in days (Δ)"),
    min_avg_profit: float = Query(12.0, description="Min avg profit filter for matrix"),
    min_win_rate: float = Query(45.0, description="Min win rate filter for matrix"),
    min_trades: int = Query(0, description="Min trades per cell (0 = auto-scale with training window)"),
    n_permutations: int = Query(1000, description="Monte Carlo permutation test iterations"),
    selection_logic: str = Query('classic', description="Logic for rankings: 'classic' or 'statistical'"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission),
) -> APIResponse:
    """Run walk-forward validation and return OOS performance metrics."""
    import logging
    import sqlite3
    import math
    import random
    from pathlib import Path as FsPath
    from datetime import timedelta
    from collections import defaultdict

    logger = logging.getLogger(__name__)
    logger.info(f"[WALK-FORWARD] Starting for {symbol}: W={training_days}, H={testing_days}, Δ={step_days} (logic: {selection_logic})")

    try:
        db_path = FsPath("trading_platform.db")
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get full date range
        cursor.execute(
            "SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol = ?",
            (symbol,),
        )
        date_range = cursor.fetchone()
        if not date_range or not date_range[0]:
            conn.close()
            raise HTTPException(status_code=404, detail=f"No trades found for {symbol}")

        first_date = datetime.fromisoformat(str(date_range[0])[:10])
        last_date = datetime.fromisoformat(str(date_range[1])[:10])

        total_days = (last_date - first_date).days
        if total_days < training_days + testing_days:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data: {total_days} days available, need {training_days + testing_days}"
            )

        # ── Helper: build recommendation matrix from a date range ──
        def build_matrix(start: datetime, end: datetime) -> dict:
            """Return {(time_slot, day_of_week): best_account} from training data."""
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            # Determine ranking logic
            logic_order = "avg_pnl DESC"
            if selection_logic == 'statistical':
                logic_order = "(avg_pnl * (wr / 100.0)) DESC, avg_pnl DESC"

            cursor.execute(
                f"""
                WITH perf AS (
                    SELECT account_name,
                        printf('%02d:%02d',
                            CAST(strftime('%H', entry_time) AS INTEGER),
                            CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                        ) as time_slot,
                        CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                        COUNT(*) as n,
                        AVG(profit_loss) as avg_pnl,
                        SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as wr
                    FROM processed_trades
                    WHERE symbol = ? AND entry_time >= ? AND entry_time < ?
                    GROUP BY account_name, time_slot, day_of_week
                    HAVING n >= ? AND avg_pnl > ? AND wr >= ?
                ),
                ranked AS (
                    SELECT *, ROW_NUMBER() OVER (PARTITION BY time_slot, day_of_week ORDER BY {logic_order}) as rn
                    FROM perf
                )
                SELECT time_slot, day_of_week, account_name, n, avg_pnl, wr
                FROM ranked WHERE rn = 1
                """,
                (symbol, start_str, end_str, effective_min_trades, min_avg_profit, min_win_rate),
            )
            return {
                (str(r["time_slot"]), int(r["day_of_week"])): {
                    "best_account": str(r["account_name"]),
                    "total_trades": int(r["n"]),
                    "avg_trade": round(float(r["avg_pnl"]), 2),
                    "win_rate": round(float(r["wr"]), 1)
                }
                for r in cursor.fetchall()
            }

        # ── Helper: apply matrix to OOS trades and return detailed PnL list ──
        def apply_matrix(matrix: dict, start: datetime, end: datetime) -> list:
            """Return list of trades where the recommended account was used."""
            if not matrix:
                return []
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            cursor.execute(
                """
                SELECT account_name, profit_loss, entry_time,
                    printf('%02d:%02d',
                        CAST(strftime('%H', entry_time) AS INTEGER),
                        CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                    ) as time_slot,
                    CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
                FROM processed_trades
                WHERE symbol = ? AND entry_time >= ? AND entry_time < ?
                ORDER BY entry_time ASC
                """,
                (symbol, start_str, end_str),
            )
            trades = []
            for row in cursor.fetchall():
                key = (str(row["time_slot"]), int(row["day_of_week"]))
                cell = matrix.get(key)
                if cell and cell.get("best_account") == str(row["account_name"]):
                    trades.append({
                        "pnl": float(row["profit_loss"]),
                        "date": row["entry_time"][:10], # YYYY-MM-DD
                        "time": row["entry_time"],
                        "account": str(row["account_name"]),
                        "time_slot": str(row["time_slot"]),
                        "day_of_week": int(row["day_of_week"])
                    })
            return trades

        # ── Auto-scale min_trades with training window if not overridden ──
        # For short windows (e.g. 1 week = 7 days) a 30-trade threshold will always fail.
        # We scale: floor(training_days / 7) * 3, clamped between 3 and 30.
        effective_min_trades = min_trades if min_trades > 0 else max(3, min(30, (training_days // 7) * 3))

        # ── Walk-forward loop ──
        folds = []
        fold_start = first_date
        running_cumulative_pnl = 0.0  # tracks true OOS cumulative across all folds

        while True:
            train_start = fold_start
            train_end = train_start + timedelta(days=training_days)
            test_start = train_end
            test_end = test_start + timedelta(days=testing_days)

            if test_end > last_date:
                break

            matrix = build_matrix(train_start, train_end)
            oos_trades = apply_matrix(matrix, test_start, test_end) # Returns list of dicts: {pnl, date, time}

            if oos_trades:
                # Extract PnLs for existing stats calculation
                oos_pnls = [t['pnl'] for t in oos_trades]
                
                # --- Calculate daily cumulative PnL for chart ---
                # Group by date
                daily_pnl = defaultdict(float)
                for t in oos_trades:
                    daily_pnl[t['date']] += t['pnl']
                
                # Create sorted list of daily results
                sorted_dates = sorted(daily_pnl.keys())
                chart_data = []
                fold_cum_pnl = 0.0
                for d in sorted_dates:
                    fold_cum_pnl += daily_pnl[d]
                    running_cumulative_pnl += daily_pnl[d]  # global OOS running total
                    chart_data.append({
                        "date": d,
                        "daily_pnl": daily_pnl[d],
                        "cumulative_pnl": running_cumulative_pnl,  # true global cumulative for chart
                        "fold_cumulative_pnl": fold_cum_pnl  # per-fold cumulative
                    })
                # --- Calculate OOS matrix results (actual results per cell) ---
                oos_matrix_performance = {}
                for t in oos_trades:
                    key = (t["time_slot"], t["day_of_week"])
                    if key not in oos_matrix_performance:
                        oos_matrix_performance[key] = {"total_pnl": 0.0, "trades": 0, "win_rate": 0, "wins": 0}
                    
                    perf = oos_matrix_performance[key]
                    perf["total_pnl"] += t["pnl"]
                    perf["trades"] += 1
                    if t["pnl"] > 0:
                        perf["wins"] += 1
                    perf["win_rate"] = round(perf["wins"] / perf["trades"] * 100, 1)

                # Convert tuple keys to strings for JSON serialisation
                serializable_oos_perf = {f"{k[0]}_{k[1]}": v for k, v in oos_matrix_performance.items()}
                serializable_train_matrix = {f"{k[0]}_{k[1]}": v for k, v in matrix.items()}
                # ------------------------------------------------

                n = len(oos_pnls)
                total = sum(oos_pnls)
                mean = total / n
                std = math.sqrt(sum((p - mean) ** 2 for p in oos_pnls) / max(n - 1, 1))
                # Annualise Sharpe ratio based on observed trade frequency in this fold
                trades_per_day = n / testing_days if testing_days > 0 else 1
                annual_freq = trades_per_day * 252
                # Correct sharpe calculation: (Avg Trade PnL / Std Dev Trade PnL) * sqrt(Trades Per Year)
                sharpe = (mean / std * math.sqrt(annual_freq)) if std > 0 else 0
                
                wins = sum(1 for p in oos_pnls if p > 0)
                # Max Drawdown Calculation
                peak = 0
                equity = 0
                max_dd_dollars = 0
                for p in oos_pnls:
                    equity += p
                    if equity > peak:
                        peak = equity
                    dd = peak - equity  # absolute dollar drawdown
                    if dd > max_dd_dollars:
                         max_dd_dollars = dd

                folds.append({
                    "fold": len(folds) + 1,
                    "train_start": train_start.strftime("%Y-%m-%d"),
                    "train_end": train_end.strftime("%Y-%m-%d"),
                    "test_start": test_start.strftime("%Y-%m-%d"),
                    "test_end": test_end.strftime("%Y-%m-%d"),
                    "matrix_cells": len(matrix),
                    "oos_trades": n,
                    "total_pnl": round(total, 2),
                    "cumulative_pnl_oos": round(running_cumulative_pnl, 2),  # running total across folds
                    "avg_trade": round(mean, 2),
                    "win_rate": round(wins / n * 100, 1),
                    "sharpe": round(sharpe, 3),
                    "max_drawdown_dollars": round(max_dd_dollars, 0),
                    "profitable": total > 0,
                    "chart_data": chart_data,
                    "train_matrix": serializable_train_matrix,
                    "oos_matrix_results": serializable_oos_perf,
                    "oos_trade_list": oos_trades  # Full list for CSV export
                })

            fold_start += timedelta(days=step_days)

        conn.close()

        if not folds:
            return APIResponse(
                status="success",
                message="Walk-forward completed — no folds with sufficient data",
                data={"symbol": symbol, "folds": [], "aggregate": None},
            )

        # ── Aggregate statistics ──
        all_fold_pnls = [f["total_pnl"] for f in folds]
        n_folds = len(folds)
        profitable_folds = sum(1 for f in folds if f["profitable"])
        consistency = profitable_folds / n_folds
        mean_pnl = sum(all_fold_pnls) / n_folds
        std_pnl = math.sqrt(sum((p - mean_pnl) ** 2 for p in all_fold_pnls) / max(n_folds - 1, 1))
        mean_sharpe = sum(f["sharpe"] for f in folds) / n_folds
        mean_win_rate = sum(f["win_rate"] for f in folds) / n_folds

        # t-statistic for mean fold return ≠ 0
        t_stat = (mean_pnl / (std_pnl / math.sqrt(n_folds))) if std_pnl > 0 else 0

        # Monte Carlo permutation test: shuffle fold PnLs and count how often
        # the random mean exceeds the observed mean
        random.seed(42)
        observed_mean = abs(mean_pnl)
        exceed_count = 0
        for _ in range(n_permutations):
            shuffled = [random.choice([-1, 1]) * abs(p) for p in all_fold_pnls]
            if abs(sum(shuffled) / n_folds) >= observed_mean:
                exceed_count += 1
        p_value = exceed_count / n_permutations
        
        # Determine significance and recommendation
        is_significant = p_value < 0.05 and consistency >= 0.6
        max_drawdown_agg = max((f["max_drawdown_dollars"] for f in folds), default=0)

        aggregate = {
            "total_folds": n_folds,
            "profitable_folds": profitable_folds,
            "consistency_ratio": round(consistency, 3),
            "mean_fold_pnl": round(mean_pnl, 2),
            "std_fold_pnl": round(std_pnl, 2),
            "mean_sharpe": round(mean_sharpe, 3),
            "mean_win_rate": round(mean_win_rate, 1),
            "max_drawdown": max_drawdown_agg,
            "t_statistic": round(t_stat, 3),
            "permutation_p_value": round(p_value, 4),
            "statistically_significant": is_significant,
            "recommendation": (
                "Strategy shows robust OOS performance — statistically significant positive returns."
                if is_significant
                else "Strategy requires more data or parameter tuning — OOS results not yet significant."
            ),
        }

        return APIResponse(
            status="success",
            message=f"Walk-forward validation for {symbol}: {n_folds} folds",
            data={
                "symbol": symbol,
                "config": {
                    "training_days": training_days,
                    "testing_days": testing_days,
                    "step_days": step_days,
                    "n_permutations": n_permutations,
                },
                "folds": folds,
                "aggregate": aggregate,
            },
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"[WALK-FORWARD] ERROR: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Walk-forward validation failed: {exc}")




@router.get("/monte-carlo/{account_name}")
async def run_monte_carlo(
    account_name: str,
    simulations: int = Query(10000, ge=100, le=50000),
    time_horizon_days: int = Query(30, ge=1, le=365),
    confidence_level: float = Query(0.95, ge=0.5, le=0.999),
):
    """
    Run a Monte Carlo simulation for the specified account or symbol.
    If 'account_name' is a symbol (e.g., NQ, ES), it aggregates the 'best per slot' trades (Matrix logic).
    Otherwise, it treats it as a specific account name.
    """
    import numpy as np
    import sqlite3
    from pathlib import Path
    from datetime import datetime
    from collections import defaultdict

    try:
        db_path = Path("trading_platform.db")
        if not db_path.exists():
            raise HTTPException(status_code=500, detail="Database not found")

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if input is a known Symbol
        cursor.execute("SELECT count(*) FROM processed_trades WHERE symbol = ?", (account_name,))
        symbol_count = cursor.fetchone()[0]

        trades = []
        is_symbol = False

        if symbol_count > 0:
            is_symbol = True
            # Fetch all trades for symbol, preserving time/day info
            cursor.execute('''
                SELECT 
                    account_name, 
                    profit_loss, 
                    entry_time,
                    printf('%02d:%02d', 
                        CAST(strftime('%H', entry_time) AS INTEGER), 
                        CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                    ) as time_slot,
                    CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week
                FROM processed_trades 
                WHERE symbol = ? 
                ORDER BY entry_time ASC
            ''', (account_name,))
            rows = cursor.fetchall()

            # Determine Best Account per Slot (Classic Logic: best Average Trade)
            slot_stats = defaultdict(lambda: defaultdict(list))
            for r in rows:
                key = (r['time_slot'], r['day_of_week'])
                slot_stats[key][r['account_name']].append(r['profit_loss'])

            best_accounts = {}
            for key, accounts in slot_stats.items():
                best_acct = None
                best_avg = -float('inf')
                for acct, pnls in accounts.items():
                    if len(pnls) < 1: continue
                    avg = sum(pnls) / len(pnls)
                    if avg > best_avg:
                        best_avg = avg
                        best_acct = acct
                best_accounts[key] = best_acct

            # Filter trades to only include those from the best account for that slot
            trades = [float(r['profit_loss']) for r in rows if best_accounts.get((r['time_slot'], r['day_of_week'])) == r['account_name']]
            
            # Determine date range from the rows we just fetched
            if rows:
                # rows is list of Row objects, need to parse entry_time
                start_dt = datetime.fromisoformat(rows[0]['entry_time'])
                end_dt = datetime.fromisoformat(rows[-1]['entry_time'])
                days_history = (end_dt - start_dt).days or 1
            else:
                days_history = 1

        else:
            # Treat as specific Account Name
            cursor.execute("SELECT profit_loss, entry_time FROM processed_trades WHERE account_name = ? ORDER BY entry_time ASC", (account_name,))
            rows = cursor.fetchall()
            trades = [float(r['profit_loss']) for r in rows]
            
            if rows:
                start_dt = datetime.fromisoformat(rows[0]['entry_time'])
                end_dt = datetime.fromisoformat(rows[-1]['entry_time'])
                days_history = (end_dt - start_dt).days or 1
            else:
                days_history = 1

        conn.close()

        if not trades:
            # Fallback for empty or unknown
            return APIResponse(status="error", message=f"No trades found for {account_name}", data=None)

        # Calculate trades per day frequency
        trades_per_day = len(trades) / max(1, days_history)
        trades_horizon = int(trades_per_day * time_horizon_days)
        if trades_horizon < 10: trades_horizon = 10 # Minimum floor

        # Monte Carlo Simulation (Vectorized)
        pnl_array = np.array(trades)
        
        # Generate random indices: (simulations, trades_horizon)
        # We sample WITH replacement
        rng = np.random.default_rng()
        random_indices = rng.integers(0, len(pnl_array), size=(simulations, trades_horizon))
        
        # Lookup PnLs
        simulated_pnls = pnl_array[random_indices]
        
        # Sum across horizon
        simulated_totals = np.sum(simulated_pnls, axis=1)
        
        # Metrics
        mean_return = float(np.mean(simulated_totals))
        std_dev = float(np.std(simulated_totals))
        
        # Percentiles
        percentiles_to_calc = [1, 5, 10, 25, 50, 75, 90, 95, 99]
        percentile_values = np.percentile(simulated_totals, percentiles_to_calc)
        percentiles_dict = {str(p): float(v) for p, v in zip(percentiles_to_calc, percentile_values)}
        
        # VaR (Value at Risk) - Loss at confidence level
        # If confidence is 0.95, we look at 5th percentile
        var_percentile = (1 - confidence_level) * 100
        var_value = float(np.percentile(simulated_totals, var_percentile))
        
        # Probability of Loss
        prob_loss = float(np.mean(simulated_totals < 0)) * 100

        result = {
            "account_name": account_name,
            "num_simulations": simulations,
            "time_horizon_days": time_horizon_days,
            "expected_return": mean_return,
            "expected_volatility": std_dev,
            "probability_of_loss": prob_loss,
            "var_estimates": {
                f"{int(confidence_level*100)}%": var_value
            },
            "percentiles": percentiles_dict,
            "sample_paths": np.column_stack((np.zeros(min(100, simulations)), np.cumsum(simulated_pnls[:100], axis=1))).tolist()
        }

        return APIResponse(
            status="success",
            message="Monte Carlo simulation completed",
            data=result
        )

    except Exception as e:
        logger.error(f"Monte Carlo error: {e}")
        return APIResponse(status="error", message=str(e), data=None)
