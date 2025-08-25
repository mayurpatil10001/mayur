"""
Pydantic models for account-related API endpoints.

This module contains request/response models for account management endpoints.

Requirements: 10.1, 10.4
"""

from datetime import datetime
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, validator


class AccountResponse(BaseModel):
    """Account response model."""
    
    name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Trading symbol",
        example="NQ"
    )
    
    total_trades: int = Field(
        description="Total number of trades",
        example=150
    )
    
    first_trade_date: datetime = Field(
        description="Date of first trade",
        example="2024-01-01T00:00:00Z"
    )
    
    last_trade_date: datetime = Field(
        description="Date of last trade",
        example="2024-12-31T23:59:59Z"
    )
    
    total_pnl: float = Field(
        description="Total aggregated profit/loss",
        example=15000.50
    )
    
    best_day_of_week: Optional[int] = Field(
        default=None,
        description="Best trading day of week (0=Monday, 6=Sunday)",
        example=1
    )
    
    best_hour_of_day: Optional[int] = Field(
        default=None,
        description="Best trading hour of day (0-23)",
        example=14
    )
    
    is_active: bool = Field(
        description="Whether account is active",
        example=True
    )
    
    @property
    def trading_days(self) -> int:
        """Calculate number of trading days."""
        return (self.last_trade_date - self.first_trade_date).days + 1
    
    @property
    def trades_per_day(self) -> float:
        """Calculate average trades per day."""
        return self.total_trades / self.trading_days if self.trading_days > 0 else 0.0


class AccountCreateRequest(BaseModel):
    """Account creation request model."""
    
    name: str = Field(
        description="Account name",
        example="IPS_TM_15",
        min_length=1,
        max_length=50
    )
    
    symbol: str = Field(
        description="Trading symbol",
        example="NQ",
        min_length=1,
        max_length=20
    )
    
    @validator('name')
    def validate_account_name(cls, v):
        """Validate account name format."""
        if not v.startswith('IPS_TM_'):
            raise ValueError('Account name must start with IPS_TM_')
        return v
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate trading symbol."""
        allowed_symbols = ['NQ', 'FDAX', 'ES', 'YM']
        if v not in allowed_symbols:
            raise ValueError(f'Symbol must be one of: {", ".join(allowed_symbols)}')
        return v


class AccountUpdateRequest(BaseModel):
    """Account update request model."""
    
    symbol: Optional[str] = Field(
        default=None,
        description="Trading symbol",
        example="NQ",
        min_length=1,
        max_length=20
    )
    
    is_active: Optional[bool] = Field(
        default=None,
        description="Whether account is active",
        example=True
    )
    
    @validator('symbol')
    def validate_symbol(cls, v):
        """Validate trading symbol."""
        if v is not None:
            allowed_symbols = ['NQ', 'FDAX', 'ES', 'YM']
            if v not in allowed_symbols:
                raise ValueError(f'Symbol must be one of: {", ".join(allowed_symbols)}')
        return v


class AccountListResponse(BaseModel):
    """Account list response model."""
    
    accounts: list[AccountResponse] = Field(
        description="List of accounts"
    )
    
    total_count: int = Field(
        description="Total number of accounts",
        example=5
    )


class AccountComparisonResponse(BaseModel):
    """Account comparison response model."""
    
    account_a: str = Field(
        description="First account name",
        example="IPS_TM_10"
    )
    
    account_b: str = Field(
        description="Second account name",
        example="IPS_TM_13"
    )
    
    comparison_period_start: datetime = Field(
        description="Start of comparison period",
        example="2024-01-01T00:00:00Z"
    )
    
    comparison_period_end: datetime = Field(
        description="End of comparison period",
        example="2024-12-31T23:59:59Z"
    )
    
    account_a_metrics: Dict[str, Any] = Field(
        description="Performance metrics for account A",
        example={
            "total_return": 15000.0,
            "win_rate": 0.65,
            "sharpe_ratio": 1.2,
            "max_drawdown": -2500.0
        }
    )
    
    account_b_metrics: Dict[str, Any] = Field(
        description="Performance metrics for account B",
        example={
            "total_return": 12000.0,
            "win_rate": 0.58,
            "sharpe_ratio": 0.9,
            "max_drawdown": -3200.0
        }
    )
    
    statistical_tests: Dict[str, Any] = Field(
        description="Statistical test results",
        example={
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
        }
    )
    
    conclusion: str = Field(
        description="Summary conclusion of the comparison",
        example="Account IPS_TM_10 shows statistically significant better returns"
    )