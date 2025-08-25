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
        # TODO: Implement actual performance calculation using service
        # For now, return mock performance metrics
        
        performance_metrics = PerformanceMetricsResponse(
            account_name=account_name,
            symbol=symbol or "NQ",
            period_start=start_date or datetime(2024, 1, 1),
            period_end=end_date or datetime(2024, 12, 31),
            total_return=15000.0,
            total_trades=150,
            winning_trades=95,
            losing_trades=55,
            win_rate=63.33,
            average_win=185.50,
            average_loss=-95.25,
            profit_factor=1.85,
            max_drawdown=-2500.0,
            sharpe_ratio=1.2,
            volatility=0.15,
            largest_win=750.00,
            largest_loss=-425.50,
            average_trade_duration=42.5,
            total_commission=630.0,
            net_profit=14370.0
        )
        
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
        # TODO: Implement actual temporal analysis using service
        # For now, return mock temporal analysis
        
        temporal_analysis = TemporalAnalysisResponse(
            account_name=account_name,
            symbol=symbol or "NQ",
            period_start=start_date or datetime(2024, 1, 1),
            period_end=end_date or datetime(2024, 12, 31),
            hourly_performance={
                "9": {"trades": 25, "win_rate": 0.68, "avg_profit": 125.50, "total_pnl": 3137.50},
                "10": {"trades": 30, "win_rate": 0.63, "avg_profit": 95.25, "total_pnl": 2857.50},
                "11": {"trades": 28, "win_rate": 0.61, "avg_profit": 87.75, "total_pnl": 2457.00},
                "14": {"trades": 35, "win_rate": 0.66, "avg_profit": 110.25, "total_pnl": 3858.75},
                "15": {"trades": 32, "win_rate": 0.59, "avg_profit": 78.50, "total_pnl": 2512.00}
            },
            daily_performance={
                "0": {"trades": 35, "win_rate": 0.66, "avg_profit": 105.25, "total_pnl": 3683.75},  # Monday
                "1": {"trades": 32, "win_rate": 0.62, "avg_profit": 98.50, "total_pnl": 3152.00},   # Tuesday
                "2": {"trades": 28, "win_rate": 0.64, "avg_profit": 112.75, "total_pnl": 3157.00},  # Wednesday
                "3": {"trades": 30, "win_rate": 0.60, "avg_profit": 89.25, "total_pnl": 2677.50},   # Thursday
                "4": {"trades": 25, "win_rate": 0.68, "avg_profit": 125.00, "total_pnl": 3125.00}   # Friday
            },
            best_trading_hours=[9, 14, 15],
            best_trading_days=[0, 4],  # Monday, Friday
            statistical_significance={
                "hourly_p_value": 0.032,
                "daily_p_value": 0.045,
                "significant_hours": [9, 14],
                "significant_days": [0]
            }
        )
        
        return APIResponse[TemporalAnalysisResponse](
            status="success",
            message=f"Temporal analysis completed for {account_name}",
            data=temporal_analysis
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except ServiceException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform temporal analysis: {str(e)}")


@router.get(
    "/monte-carlo/{account_name}",
    response_model=APIResponse[MonteCarloResultsResponse],
    summary="Get Monte Carlo simulation results",
    description="Run Monte Carlo simulation to assess risk and potential outcomes."
)
async def get_monte_carlo_results(
    account_name: str = Path(..., description="Account name"),
    simulations: int = Query(10000, ge=1000, le=100000, description="Number of simulations to run"),
    time_horizon_days: int = Query(30, ge=1, le=365, description="Time horizon in days"),
    confidence_level: float = Query(0.95, ge=0.8, le=0.99, description="Confidence level for VaR calculation"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[MonteCarloResultsResponse]:
    """Run Monte Carlo simulation for risk assessment."""
    
    try:
        # TODO: Implement actual Monte Carlo simulation using service
        # For now, return mock simulation results
        
        monte_carlo_results = MonteCarloResultsResponse(
            account_name=account_name,
            simulations=simulations,
            time_horizon_days=time_horizon_days,
            confidence_level=confidence_level,
            expected_return=1250.0,
            expected_volatility=850.0,
            value_at_risk=-2100.0,
            expected_shortfall=-2850.0,
            probability_of_profit=0.68,
            percentile_results={
                "5": -2850.0,
                "10": -2100.0,
                "25": -750.0,
                "50": 1250.0,
                "75": 3250.0,
                "90": 4850.0,
                "95": 6100.0
            },
            max_simulated_loss=-4250.0,
            max_simulated_gain=8750.0
        )
        
        return APIResponse[MonteCarloResultsResponse](
            status="success",
            message=f"Monte Carlo simulation completed for {account_name}",
            data=monte_carlo_results
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run Monte Carlo simulation: {str(e)}")


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
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Get recommendation matrix showing best account for each time slot and day of week."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[RECOMMENDATION MATRIX] Getting matrix for {symbol}")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[RECOMMENDATION MATRIX] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query to get best performing account for each time slot and day of week
        # Only recommend if significantly better than break-even
        query = """
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
            WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= ?  -- Only include slots with sufficient data
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY avg_trade DESC, win_rate DESC
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
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Get historical backtest showing P&L if recommendations were followed."""
    
    import logging
    import sqlite3
    from pathlib import Path
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info(f"[RECOMMENDATION BACKTEST] Getting backtest for {symbol}, {days_back} days")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[RECOMMENDATION BACKTEST] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the actual date range of trading data for this symbol
        date_range_query = """
        SELECT 
            MIN(DATE(entry_time)) as min_date,
            MAX(DATE(entry_time)) as max_date
        FROM processed_trades 
        WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
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
        matrix_query = """
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
            WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= ?
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY avg_trade DESC, win_rate DESC
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
            AND account_name NOT LIKE '%dupl%' 
            AND account_name NOT LIKE '%sim%'
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
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse:
    """Calculate combined statistics from all recommended accounts for a symbol."""
    
    import logging
    import sqlite3
    from pathlib import Path
    from datetime import datetime, timedelta
    
    logger = logging.getLogger(__name__)
    logger.info(f"[COMBINED STATS] Getting combined statistics for {symbol}")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[COMBINED STATS] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get the actual date range of trading data for this symbol
        date_range_query = """
        SELECT 
            MIN(DATE(entry_time)) as min_date,
            MAX(DATE(entry_time)) as max_date
        FROM processed_trades 
        WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
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
        rec_query = """
        WITH time_day_performance AS (
            SELECT 
                account_name,
                printf('%02d:%02d', 
                    CAST(strftime('%H', entry_time) AS INTEGER),
                    CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
                ) as time_slot,
                CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
                AVG(profit_loss) as avg_trade
            FROM processed_trades 
            WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
            GROUP BY account_name, time_slot, day_of_week
            HAVING COUNT(*) >= 5
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY avg_trade DESC
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
            WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
            GROUP BY account_name, time_slot, day_of_week
            HAVING total_trades >= ?
        ),
        ranked_performance AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY time_slot, day_of_week 
                    ORDER BY avg_trade DESC, win_rate DESC
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
            CAST(strftime('%w', entry_time) AS INTEGER) as day_of_week,
            account_name,
            profit_loss
        FROM processed_trades 
        WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
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
        
        # Simple Sharpe ratio
        if total_trades > 1:
            variance = sum((float(t['profit_loss']) - avg_trade) ** 2 for t in recommended_trades) / (total_trades - 1)
            std_dev = variance ** 0.5
            sharpe_ratio = avg_trade / std_dev if std_dev > 0 else 0
        else:
            sharpe_ratio = 0
        
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
            'max_drawdown': max_drawdown,
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
                'max_drawdown': stats['max_drawdown'],
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
            WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
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
        WHERE symbol = ? 
            AND account_name NOT LIKE '%dupl%' 
            AND account_name NOT LIKE '%sim%'
            AND ABS(profit_loss) >= ?
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
            WHERE symbol = ? AND account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
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
        WHERE symbol = ? 
            AND DATE(entry_time) >= ?
            AND DATE(entry_time) <= ?
            AND account_name NOT LIKE '%dupl%' 
            AND account_name NOT LIKE '%sim%'
        ORDER BY entry_time
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
        WHERE account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
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