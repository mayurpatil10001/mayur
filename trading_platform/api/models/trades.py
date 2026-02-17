"""
Pydantic models for trade-related API endpoints.

This module contains request/response models for trade data endpoints.

Requirements: 10.1, 10.4
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, validator
from enum import Enum


class TradeSide(str, Enum):
    """Trade side enumeration."""
    LONG = "LONG"
    SHORT = "SHORT"


class TradeResponse(BaseModel):
    """Trade response model."""
    
    trade_id: str = Field(
        description="Unique trade identifier",
        example="TRADE_001_20240101_001"
    )
    
    time_slot: str = Field(
        description="30-minute time slot (HH:mm)",
        example="09:30"
    )
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Trading symbol",
        example="NQ"
    )
    
    entry_time: datetime = Field(
        description="Trade entry timestamp",
        example="2024-01-01T09:30:00Z"
    )
    
    exit_time: datetime = Field(
        description="Trade exit timestamp",
        example="2024-01-01T10:15:00Z"
    )
    
    entry_price: float = Field(
        description="Entry price",
        example=15250.50
    )
    
    exit_price: float = Field(
        description="Exit price",
        example=15275.25
    )
    
    quantity: int = Field(
        description="Trade quantity",
        example=2
    )
    
    side: TradeSide = Field(
        description="Trade side (LONG or SHORT)",
        example=TradeSide.LONG
    )
    
    profit_loss: float = Field(
        description="Profit/loss amount",
        example=49.50
    )
    
    commission: float = Field(
        description="Commission paid",
        example=4.20
    )
    
    duration_minutes: int = Field(
        description="Trade duration in minutes",
        example=45
    )
    
    hour_of_day: int = Field(
        description="Hour of day when trade was entered",
        example=9,
        ge=0,
        le=23
    )
    
    day_of_week: int = Field(
        description="Day of week when trade was entered (0=Monday)",
        example=0,
        ge=0,
        le=6
    )
    
    @property
    def net_profit_loss(self) -> float:
        """Calculate net profit/loss after commission."""
        return self.profit_loss - self.commission
    
    @property
    def return_percentage(self) -> float:
        """Calculate return percentage."""
        if self.entry_price == 0:
            return 0.0
        return (self.profit_loss / (self.entry_price * self.quantity)) * 100


class TradeListRequest(BaseModel):
    """Trade list request parameters."""
    
    account_name: Optional[str] = Field(
        default=None,
        description="Filter by account name",
        example="IPS_TM_10"
    )
    
    symbol: Optional[str] = Field(
        default=None,
        description="Filter by symbol",
        example="NQ"
    )
    
    start_date: Optional[datetime] = Field(
        default=None,
        description="Filter trades from this date",
        example="2024-01-01T00:00:00Z"
    )
    
    end_date: Optional[datetime] = Field(
        default=None,
        description="Filter trades until this date",
        example="2024-12-31T23:59:59Z"
    )
    
    min_profit: Optional[float] = Field(
        default=None,
        description="Filter trades with profit >= this amount",
        example=0.0
    )
    
    max_profit: Optional[float] = Field(
        default=None,
        description="Filter trades with profit <= this amount",
        example=1000.0
    )
    
    side: Optional[TradeSide] = Field(
        default=None,
        description="Filter by trade side",
        example=TradeSide.LONG
    )
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate that end_date is after start_date."""
        if v and 'start_date' in values and values['start_date']:
            if v <= values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class TradeStatsResponse(BaseModel):
    """Trade statistics response model."""
    
    total_trades: int = Field(
        description="Total number of trades",
        example=150
    )
    
    winning_trades: int = Field(
        description="Number of winning trades",
        example=95
    )
    
    losing_trades: int = Field(
        description="Number of losing trades",
        example=55
    )
    
    win_rate: float = Field(
        description="Win rate percentage",
        example=63.33
    )
    
    total_profit_loss: float = Field(
        description="Total profit/loss",
        example=12500.75
    )
    
    average_win: float = Field(
        description="Average winning trade amount",
        example=185.50
    )
    
    average_loss: float = Field(
        description="Average losing trade amount",
        example=-95.25
    )
    
    largest_win: float = Field(
        description="Largest winning trade",
        example=750.00
    )
    
    largest_loss: float = Field(
        description="Largest losing trade",
        example=-425.50
    )
    
    profit_factor: float = Field(
        description="Profit factor (gross profit / gross loss)",
        example=1.85
    )
    
    average_duration_minutes: float = Field(
        description="Average trade duration in minutes",
        example=42.5
    )


class SierraChartImportRequest(BaseModel):
    """SierraChart data import request."""
    
    file_paths: Optional[List[str]] = Field(
        default=None,
        description="Specific file paths to import (if not provided, scans default directories)",
        example=[
            "D:\\SierraChart_Simulated_Feed\\SavedTradeActivity\\file1.txt",
            "D:\\SierraChart_Delayed_Simulated\\SavedTradeActivity\\file2.txt"
        ]
    )
    
    force_reimport: bool = Field(
        default=False,
        description="Force reimport of already processed files",
        example=False
    )
    
    validate_only: bool = Field(
        default=False,
        description="Only validate files without importing",
        example=False
    )


class ImportStatusResponse(BaseModel):
    """Import operation status response."""
    
    import_id: str = Field(
        description="Import operation ID",
        example="import_20240101_123456"
    )
    
    status: str = Field(
        description="Import status",
        example="completed"
    )
    
    started_at: datetime = Field(
        description="Import start time",
        example="2024-01-01T12:34:56Z"
    )
    
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Import completion time",
        example="2024-01-01T12:45:30Z"
    )
    
    files_processed: int = Field(
        description="Number of files processed",
        example=5
    )
    
    records_imported: int = Field(
        description="Number of records imported",
        example=1250
    )
    
    records_skipped: int = Field(
        description="Number of records skipped",
        example=25
    )
    
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered",
        example=["File not found: missing_file.txt"]
    )
    
    progress_percentage: float = Field(
        description="Import progress percentage",
        example=100.0,
        ge=0.0,
        le=100.0
    )