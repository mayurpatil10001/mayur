"""
Account management API endpoints.

This module provides REST endpoints for managing trading accounts,
including CRUD operations and account-specific analytics.

Requirements: 7.1, 10.1, 10.3
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from ..dependencies import (
    get_database_session,
    get_account_comparator,
    require_read_permission,
    require_write_permission
)
from ..models.common import APIResponse, PaginatedResponse, PaginationParams
from ..models.accounts import (
    AccountResponse,
    AccountCreateRequest,
    AccountUpdateRequest,
    AccountListResponse,
    AccountComparisonResponse
)
from ..exceptions import DataNotFoundException, ValidationException
from ...services.account_comparison_service import AccountComparisonService
from ...models.trading import Account


router = APIRouter()


@router.get(
    "/debug",
    summary="Debug accounts endpoint",
    description="Debug endpoint to check database connection and account data."
)
async def debug_accounts():
    """Debug endpoint to check database connection and account data."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info("[ACCOUNTS DEBUG] Starting debug check")
    
    debug_info = {
        "timestamp": datetime.now().isoformat(),
        "database_path": None,
        "database_exists": False,
        "database_accessible": False,
        "total_trades": 0,
        "account_symbol_combinations": 0,
        "unique_accounts": 0,
        "sample_accounts": [],
        "errors": []
    }
    
    try:
        # Check database file
        db_path = Path("trading_platform.db")
        debug_info["database_path"] = str(db_path.absolute())
        debug_info["database_exists"] = db_path.exists()
        
        if not db_path.exists():
            debug_info["errors"].append("Database file not found")
            return debug_info
        
        # Connect to database
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        debug_info["database_accessible"] = True
        
        # Get total trades
        cursor.execute("SELECT COUNT(*) as count FROM processed_trades")
        debug_info["total_trades"] = cursor.fetchone()["count"]
        
        # Get account-symbol combinations
        cursor.execute("""
            SELECT COUNT(*) as count FROM (
                SELECT DISTINCT account_name, symbol 
                FROM processed_trades 
                WHERE account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
            )
        """)
        debug_info["account_symbol_combinations"] = cursor.fetchone()["count"]
        
        # Get unique accounts
        cursor.execute("""
            SELECT COUNT(DISTINCT account_name) as count
            FROM processed_trades 
            WHERE account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
        """)
        debug_info["unique_accounts"] = cursor.fetchone()["count"]
        
        # Get sample accounts
        cursor.execute("""
            SELECT 
                account_name,
                symbol,
                COUNT(*) as total_trades,
                MIN(entry_time) as first_trade,
                MAX(entry_time) as last_trade
            FROM processed_trades 
            WHERE account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
            GROUP BY account_name, symbol 
            ORDER BY account_name, symbol
            LIMIT 10
        """)
        
        sample_data = cursor.fetchall()
        debug_info["sample_accounts"] = [dict(row) for row in sample_data]
        
        conn.close()
        
    except Exception as e:
        debug_info["errors"].append(f"Database error: {str(e)}")
        logger.error(f"[ACCOUNTS DEBUG] Error: {e}", exc_info=True)
    
    logger.info(f"[ACCOUNTS DEBUG] Debug info: {debug_info}")
    return debug_info


@router.get(
    "/",
    response_model=APIResponse[PaginatedResponse[AccountResponse]],
    summary="List all trading accounts",
    description="Retrieve a paginated list of all trading accounts with optional filtering."
)
async def list_accounts(
    pagination: PaginationParams = Depends(),
    symbol: Optional[str] = Query(None, description="Filter by symbol (e.g., NQ, FDAX)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[PaginatedResponse[AccountResponse]]:
    """List all trading accounts with pagination and filtering."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[ACCOUNTS API] Starting list_accounts - symbol={symbol}, is_active={is_active}, page={pagination.page}, size={pagination.size}")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        logger.info(f"[ACCOUNTS API] Connecting to database: {db_path.absolute()}")
        
        if not db_path.exists():
            logger.error(f"[ACCOUNTS API] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # No need for account name conversion - we have proper names now
        
        # Optimized query to get account summary from processed_trades
        base_query = """
        SELECT 
            account_name,
            symbol,
            COUNT(*) as total_trades,
            MIN(entry_time) as first_trade_date,
            MAX(entry_time) as last_trade_date,
            SUM(profit_loss) as total_pnl,
            1 as is_active
        FROM processed_trades 
        WHERE account_name NOT LIKE '%dupl%' AND account_name NOT LIKE '%sim%'
        """
        
        params = []
        if symbol:
            base_query += " AND symbol = ?"
            params.append(symbol)
            
        base_query += " GROUP BY account_name, symbol ORDER BY account_name, symbol"
        
        logger.info(f"[ACCOUNTS API] Executing optimized query: {base_query}")
        logger.info(f"[ACCOUNTS API] Query params: {params}")
        
        cursor.execute(base_query, params)
        rows = cursor.fetchall()
        
        logger.info(f"[ACCOUNTS API] Found {len(rows)} account-symbol combinations")
        
        # Get timing data from temporal_performance table
        logger.info("[ACCOUNTS API] Fetching temporal performance data...")
        timing_query = """
        SELECT 
            account_name,
            base_symbol,
            day_of_week,
            hour_of_day,
            average_profit_loss,
            ROW_NUMBER() OVER (PARTITION BY account_name, base_symbol ORDER BY average_profit_loss DESC) as rn
        FROM temporal_performance
        """
        
        cursor.execute(timing_query)
        timing_rows = cursor.fetchall()
        
        # Build lookup for best day and hour for each account-symbol combination
        timing_lookup = {}
        for timing_row in timing_rows:
            if timing_row['rn'] == 1:  # Only take the best performing combination
                key = (timing_row['account_name'], timing_row['base_symbol'])
                if key not in timing_lookup:
                    timing_lookup[key] = {}
                
                # Store both day and hour data - we'll pick the best one for each
                if 'best_day' not in timing_lookup[key] or timing_row['average_profit_loss'] > timing_lookup[key].get('best_day_pnl', float('-inf')):
                    timing_lookup[key]['best_day'] = timing_row['day_of_week']
                    timing_lookup[key]['best_day_pnl'] = timing_row['average_profit_loss']
                
                if 'best_hour' not in timing_lookup[key] or timing_row['average_profit_loss'] > timing_lookup[key].get('best_hour_pnl', float('-inf')):
                    timing_lookup[key]['best_hour'] = timing_row['hour_of_day']
                    timing_lookup[key]['best_hour_pnl'] = timing_row['average_profit_loss']
        
        # Get separate best day and best hour for each account-symbol
        best_day_query = """
        SELECT 
            account_name,
            base_symbol,
            day_of_week,
            average_profit_loss,
            ROW_NUMBER() OVER (PARTITION BY account_name, base_symbol ORDER BY average_profit_loss DESC) as rn
        FROM temporal_performance
        """
        
        cursor.execute(best_day_query)
        day_rows = cursor.fetchall()
        
        best_hour_query = """
        SELECT 
            account_name,
            base_symbol,
            hour_of_day,
            average_profit_loss,
            ROW_NUMBER() OVER (PARTITION BY account_name, base_symbol ORDER BY average_profit_loss DESC) as rn
        FROM temporal_performance
        """
        
        cursor.execute(best_hour_query)
        hour_rows = cursor.fetchall()
        
        # Build separate lookups for best day and best hour
        best_day_lookup = {}
        for day_row in day_rows:
            if day_row['rn'] == 1:
                key = (day_row['account_name'], day_row['base_symbol'])
                best_day_lookup[key] = day_row['day_of_week']
        
        best_hour_lookup = {}
        for hour_row in hour_rows:
            if hour_row['rn'] == 1:
                key = (hour_row['account_name'], hour_row['base_symbol'])
                best_hour_lookup[key] = hour_row['hour_of_day']
        
        logger.info(f"[ACCOUNTS API] Loaded timing data for {len(best_day_lookup)} account-symbol combinations")
        
        # Convert to AccountResponse objects
        accounts = []
        for row in rows:
            try:
                # Get timing data for this account-symbol combination
                key = (row['account_name'], row['symbol'])
                best_day = best_day_lookup.get(key)
                best_hour = best_hour_lookup.get(key)
                
                account = AccountResponse(
                    name=row['account_name'],
                    symbol=row['symbol'],
                    total_trades=row['total_trades'],
                    first_trade_date=datetime.fromisoformat(row['first_trade_date'].replace('Z', '+00:00')) if row['first_trade_date'] else None,
                    last_trade_date=datetime.fromisoformat(row['last_trade_date'].replace('Z', '+00:00')) if row['last_trade_date'] else None,
                    total_pnl=float(row['total_pnl']) if row['total_pnl'] else 0.0,
                    best_day_of_week=best_day,
                    best_hour_of_day=best_hour,
                    is_active=bool(row['is_active'])
                )
                accounts.append(account)
                logger.debug(f"[ACCOUNTS API] Added account: {account.name} ({account.symbol}) - {account.total_trades} trades, P&L: ${account.total_pnl:.2f}")
            except Exception as e:
                logger.error(f"[ACCOUNTS API] Error processing row {dict(row)}: {e}")
                continue
        
        conn.close()
        
        # Apply is_active filter if specified
        if is_active is not None:
            accounts = [acc for acc in accounts if acc.is_active == is_active]
            logger.info(f"[ACCOUNTS API] After is_active filter: {len(accounts)} accounts")
        
        # Apply pagination
        total = len(accounts)
        start_idx = pagination.offset
        end_idx = start_idx + pagination.size
        page_accounts = accounts[start_idx:end_idx]
        
        logger.info(f"[ACCOUNTS API] Pagination: total={total}, start={start_idx}, end={end_idx}, page_size={len(page_accounts)}")
        
        paginated_response = PaginatedResponse[AccountResponse](
            items=page_accounts,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=(total + pagination.size - 1) // pagination.size,
            has_next=end_idx < total,
            has_prev=pagination.page > 1
        )
        
        logger.info(f"[ACCOUNTS API] SUCCESS: Returning {len(page_accounts)} accounts (page {pagination.page} of {paginated_response.pages})")
        
        return APIResponse[PaginatedResponse[AccountResponse]](
            status="success",
            message=f"Retrieved {len(page_accounts)} accounts",
            data=paginated_response
        )
        
    except Exception as e:
        logger.error(f"[ACCOUNTS API] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve accounts: {str(e)}")


@router.get(
    "/{account_name}",
    response_model=APIResponse[AccountResponse],
    summary="Get account details",
    description="Retrieve detailed information for a specific trading account."
)
async def get_account(
    account_name: str = Path(..., description="Account name (e.g., IPS_TM_10)"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[AccountResponse]:
    """Get detailed information for a specific account."""
    
    try:
        # TODO: Implement actual database query using MCP
        # For now, return mock data
        if account_name == "IPS_TM_10":
            account = AccountResponse(
                name="IPS_TM_10",
                symbol="NQ",
                total_trades=150,
                first_trade_date=datetime(2024, 1, 1),
                last_trade_date=datetime(2024, 12, 31),
                total_pnl=15000.0,
                best_day_of_week=1,
                best_hour_of_day=14,
                is_active=True
            )
        elif account_name == "IPS_TM_13":
            account = AccountResponse(
                name="IPS_TM_13",
                symbol="FDAX",
                total_trades=89,
                first_trade_date=datetime(2024, 2, 1),
                last_trade_date=datetime(2024, 12, 30),
                total_pnl=12000.0,
                best_day_of_week=2,
                best_hour_of_day=10,
                is_active=True
            )
        else:
            raise DataNotFoundException("Account", account_name)
        
        return APIResponse[AccountResponse](
            status="success",
            message=f"Retrieved account {account_name}",
            data=account
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve account: {str(e)}")


@router.post(
    "/",
    response_model=APIResponse[AccountResponse],
    status_code=201,
    summary="Create new account",
    description="Create a new trading account with validation."
)
async def create_account(
    account_data: AccountCreateRequest,
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[AccountResponse]:
    """Create a new trading account."""
    
    try:
        # TODO: Implement actual database creation using MCP
        # For now, return mock response
        
        # Validate account doesn't already exist
        # This would be a database check in real implementation
        
        created_account = AccountResponse(
            name=account_data.name,
            symbol=account_data.symbol,
            total_trades=0,
            first_trade_date=datetime.now(),
            last_trade_date=datetime.now(),
            total_pnl=0.0,
            best_day_of_week=None,
            best_hour_of_day=None,
            is_active=True
        )
        
        return APIResponse[AccountResponse](
            status="success",
            message=f"Account {account_data.name} created successfully",
            data=created_account
        )
        
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create account: {str(e)}")


@router.put(
    "/{account_name}",
    response_model=APIResponse[AccountResponse],
    summary="Update account",
    description="Update an existing trading account."
)
async def update_account(
    account_name: str = Path(..., description="Account name to update"),
    account_data: AccountUpdateRequest = ...,
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[AccountResponse]:
    """Update an existing trading account."""
    
    try:
        # TODO: Implement actual database update using MCP
        # For now, return mock response
        
        # Check if account exists
        if account_name not in ["IPS_TM_10", "IPS_TM_13"]:
            raise DataNotFoundException("Account", account_name)
        
        updated_account = AccountResponse(
            name=account_name,
            symbol=account_data.symbol if account_data.symbol else "NQ",
            total_trades=150,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 12, 31),
            total_pnl=15000.0,
            best_day_of_week=1,
            best_hour_of_day=14,
            is_active=account_data.is_active if account_data.is_active is not None else True
        )
        
        return APIResponse[AccountResponse](
            status="success",
            message=f"Account {account_name} updated successfully",
            data=updated_account
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except ValidationException as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update account: {str(e)}")


@router.delete(
    "/{account_name}",
    response_model=APIResponse[None],
    summary="Delete account",
    description="Delete a trading account and all associated data."
)
async def delete_account(
    account_name: str = Path(..., description="Account name to delete"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_write_permission)
) -> APIResponse[None]:
    """Delete a trading account."""
    
    try:
        # TODO: Implement actual database deletion using MCP
        # For now, return mock response
        
        # Check if account exists
        if account_name not in ["IPS_TM_10", "IPS_TM_13"]:
            raise DataNotFoundException("Account", account_name)
        
        return APIResponse[None](
            status="success",
            message=f"Account {account_name} deleted successfully"
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")


@router.get(
    "/{account_name}/hourly-breakdown",
    response_model=APIResponse[List[Dict[str, Any]]],
    summary="Get hourly breakdown for account",
    description="Get 30-minute interval breakdown for a specific account and symbol."
)
async def get_hourly_breakdown(
    account_name: str = Path(..., description="Account name"),
    symbol: str = Query(..., description="Trading symbol (e.g., NQ, CL)"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[List[Dict[str, Any]]]:
    """Get hourly breakdown for a specific account and symbol."""
    
    import logging
    import sqlite3
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    logger.info(f"[HOURLY BREAKDOWN] Getting data for {account_name} ({symbol})")
    
    try:
        # Connect to SQLite database
        db_path = Path("trading_platform.db")
        
        if not db_path.exists():
            logger.error(f"[HOURLY BREAKDOWN] Database file not found: {db_path.absolute()}")
            raise HTTPException(status_code=500, detail="Database file not found")
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query to get 30-minute interval breakdown with comprehensive trading metrics
        query = """
        SELECT 
            printf('%02d:%02d', 
                CAST(strftime('%H', entry_time) AS INTEGER),
                CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
            ) as time_slot,
            SUM(profit_loss) as net_pnl,
            COUNT(*) as total_trades,
            ROUND(AVG(profit_loss), 2) as avg_trade,
            ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 1) as win_percentage,
            ROUND(AVG(CASE WHEN profit_loss > 0 THEN profit_loss END), 2) as avg_winner,
            ROUND(AVG(CASE WHEN profit_loss < 0 THEN profit_loss END), 2) as avg_loser,
            MAX(profit_loss) as largest_winner,
            MIN(profit_loss) as largest_loser,
            CASE WHEN SUM(profit_loss) < 0 THEN SUM(profit_loss) ELSE 0 END as drawdown,
            CASE WHEN SUM(profit_loss) > 0 THEN SUM(profit_loss) ELSE 0 END as runup,
            SUM(profit_loss) as equity_peak
        FROM processed_trades 
        WHERE account_name = ? AND symbol = ?
        GROUP BY printf('%02d:%02d', 
            CAST(strftime('%H', entry_time) AS INTEGER),
            CASE WHEN CAST(strftime('%M', entry_time) AS INTEGER) < 30 THEN 0 ELSE 30 END
        )
        ORDER BY time_slot
        """
        
        cursor.execute(query, (account_name, symbol))
        rows = cursor.fetchall()
        
        # Convert to list of dictionaries
        breakdown_data = []
        for row in rows:
            breakdown_data.append({
                'time_slot': row['time_slot'],
                'net_pnl': float(row['net_pnl']) if row['net_pnl'] else 0.0,
                'total_trades': int(row['total_trades']) if row['total_trades'] else 0,
                'avg_trade': float(row['avg_trade']) if row['avg_trade'] else 0.0,
                'win_percentage': float(row['win_percentage']) if row['win_percentage'] else 0.0,
                'avg_winner': float(row['avg_winner']) if row['avg_winner'] else 0.0,
                'avg_loser': float(row['avg_loser']) if row['avg_loser'] else 0.0,
                'largest_winner': float(row['largest_winner']) if row['largest_winner'] else 0.0,
                'largest_loser': float(row['largest_loser']) if row['largest_loser'] else 0.0,
                'drawdown': float(row['drawdown']) if row['drawdown'] else 0.0,
                'runup': float(row['runup']) if row['runup'] else 0.0,
                'equity_peak': float(row['equity_peak']) if row['equity_peak'] else 0.0
            })
        
        conn.close()
        
        logger.info(f"[HOURLY BREAKDOWN] SUCCESS: Returning {len(breakdown_data)} time slots for {account_name} ({symbol})")
        
        return APIResponse[List[Dict[str, Any]]](
            status="success",
            message=f"Retrieved hourly breakdown for {account_name} ({symbol})",
            data=breakdown_data
        )
        
    except Exception as e:
        logger.error(f"[HOURLY BREAKDOWN] ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve hourly breakdown: {str(e)}")


@router.get(
    "/{account_name}/compare/{other_account_name}",
    response_model=APIResponse[AccountComparisonResponse],
    summary="Compare two accounts",
    description="Compare performance between two trading accounts statistically."
)
async def compare_accounts(
    account_name: str = Path(..., description="First account name"),
    other_account_name: str = Path(..., description="Second account name"),
    comparison_service: AccountComparisonService = Depends(get_account_comparator),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[AccountComparisonResponse]:
    """Compare performance between two trading accounts."""
    
    try:
        # TODO: Implement actual comparison using service
        # For now, return mock comparison
        
        comparison_result = AccountComparisonResponse(
            account_a=account_name,
            account_b=other_account_name,
            comparison_period_start=datetime(2024, 1, 1),
            comparison_period_end=datetime(2024, 12, 31),
            account_a_metrics={
                "total_return": 15000.0,
                "win_rate": 0.65,
                "sharpe_ratio": 1.2,
                "max_drawdown": -2500.0
            },
            account_b_metrics={
                "total_return": 12000.0,
                "win_rate": 0.58,
                "sharpe_ratio": 0.9,
                "max_drawdown": -3200.0
            },
            statistical_tests={
                "returns_t_test": {
                    "statistic": 2.15,
                    "p_value": 0.032,
                    "significant": True
                },
                "win_rate_test": {
                    "statistic": 1.87,
                    "p_value": 0.061,
                    "significant": False
                }
            },
            conclusion=f"Account {account_name} shows statistically significant better returns than {other_account_name}"
        )
        
        return APIResponse[AccountComparisonResponse](
            status="success",
            message=f"Comparison completed between {account_name} and {other_account_name}",
            data=comparison_result
        )
        
    except DataNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare accounts: {str(e)}")