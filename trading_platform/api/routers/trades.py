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
    
    try:
        # TODO: Implement actual database query using MCP
        # For now, return mock data with filtering applied
        
        mock_trades = [
            TradeResponse(
                trade_id="TRADE_001_20240101_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=datetime(2024, 1, 1, 9, 30),
                exit_time=datetime(2024, 1, 1, 10, 15),
                entry_price=15250.50,
                exit_price=15275.25,
                quantity=2,
                side=TradeSide.LONG,
                profit_loss=49.50,
                commission=4.20,
                duration_minutes=45,
                hour_of_day=9,
                day_of_week=0
            ),
            TradeResponse(
                trade_id="TRADE_002_20240101_002",
                account_name="IPS_TM_13",
                symbol="FDAX",
                entry_time=datetime(2024, 1, 1, 14, 20),
                exit_time=datetime(2024, 1, 1, 14, 35),
                entry_price=17850.00,
                exit_price=17825.50,
                quantity=1,
                side=TradeSide.SHORT,
                profit_loss=24.50,
                commission=3.50,
                duration_minutes=15,
                hour_of_day=14,
                day_of_week=0
            ),
            TradeResponse(
                trade_id="TRADE_003_20240102_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=datetime(2024, 1, 2, 10, 45),
                exit_time=datetime(2024, 1, 2, 11, 30),
                entry_price=15280.75,
                exit_price=15260.25,
                quantity=1,
                side=TradeSide.LONG,
                profit_loss=-20.50,
                commission=4.20,
                duration_minutes=45,
                hour_of_day=10,
                day_of_week=1
            )
        ]
        
        # Apply filters
        filtered_trades = mock_trades
        
        if account_name:
            filtered_trades = [t for t in filtered_trades if t.account_name == account_name]
        
        if symbol:
            filtered_trades = [t for t in filtered_trades if t.symbol == symbol]
        
        if start_date:
            filtered_trades = [t for t in filtered_trades if t.entry_time >= start_date]
        
        if end_date:
            filtered_trades = [t for t in filtered_trades if t.entry_time <= end_date]
        
        if min_profit is not None:
            filtered_trades = [t for t in filtered_trades if t.profit_loss >= min_profit]
        
        if max_profit is not None:
            filtered_trades = [t for t in filtered_trades if t.profit_loss <= max_profit]
        
        if side:
            filtered_trades = [t for t in filtered_trades if t.side == side]
        
        # Apply pagination
        total = len(filtered_trades)
        start_idx = pagination.offset
        end_idx = start_idx + pagination.size
        page_trades = filtered_trades[start_idx:end_idx]
        
        paginated_response = PaginatedResponse[TradeResponse](
            items=page_trades,
            total=total,
            page=pagination.page,
            size=pagination.size,
            pages=(total + pagination.size - 1) // pagination.size,
            has_next=end_idx < total,
            has_prev=pagination.page > 1
        )
        
        return APIResponse[PaginatedResponse[TradeResponse]](
            status="success",
            message=f"Retrieved {len(page_trades)} trades",
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
    
    try:
        # TODO: Implement actual database query using MCP
        # For now, return mock data
        
        if trade_id == "TRADE_001_20240101_001":
            trade = TradeResponse(
                trade_id="TRADE_001_20240101_001",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=datetime(2024, 1, 1, 9, 30),
                exit_time=datetime(2024, 1, 1, 10, 15),
                entry_price=15250.50,
                exit_price=15275.25,
                quantity=2,
                side=TradeSide.LONG,
                profit_loss=49.50,
                commission=4.20,
                duration_minutes=45,
                hour_of_day=9,
                day_of_week=0
            )
        else:
            raise DataNotFoundException("Trade", trade_id)
        
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
    
    try:
        # TODO: Implement actual statistics calculation using database
        # For now, return mock statistics
        
        stats = TradeStatsResponse(
            total_trades=150,
            winning_trades=95,
            losing_trades=55,
            win_rate=63.33,
            total_profit_loss=12500.75,
            average_win=185.50,
            average_loss=-95.25,
            largest_win=750.00,
            largest_loss=-425.50,
            profit_factor=1.85,
            average_duration_minutes=42.5
        )
        
        return APIResponse[TradeStatsResponse](
            status="success",
            message=f"Retrieved trade statistics for {account_name}",
            data=stats
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trade statistics: {str(e)}")