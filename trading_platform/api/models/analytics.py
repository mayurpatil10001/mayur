"""
Pydantic models for analytics-related API endpoints.

This module contains request/response models for analytics and performance metrics endpoints.

Requirements: 10.1, 10.4
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class MetricType(str, Enum):
    """Performance metric types."""
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    PROFIT_FACTOR = "profit_factor"
    VOLATILITY = "volatility"


class TimeFrame(str, Enum):
    """Time frame for analysis."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response model."""
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Trading symbol",
        example="NQ"
    )
    
    period_start: datetime = Field(
        description="Analysis period start",
        example="2024-01-01T00:00:00Z"
    )
    
    period_end: datetime = Field(
        description="Analysis period end",
        example="2024-12-31T23:59:59Z"
    )
    
    total_return: float = Field(
        description="Total return amount",
        example=15000.50
    )
    
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
        description="Win rate percentage (0-100)",
        example=63.33,
        ge=0.0,
        le=100.0
    )
    
    average_win: float = Field(
        description="Average winning trade amount",
        example=285.75
    )
    
    average_loss: float = Field(
        description="Average losing trade amount",
        example=-125.50
    )
    
    profit_factor: float = Field(
        description="Profit factor (gross profit / gross loss)",
        example=1.85
    )
    
    max_drawdown: float = Field(
        description="Maximum drawdown amount",
        example=-2500.00
    )
    
    sharpe_ratio: Optional[float] = Field(
        description="Sharpe ratio",
        example=1.25
    )
    
    volatility: float = Field(
        description="Return volatility",
        example=0.15
    )
    
    largest_win: float = Field(
        description="Largest winning trade",
        example=750.00
    )
    
    largest_loss: float = Field(
        description="Largest losing trade",
        example=-425.50
    )


class TemporalAnalysisResponse(BaseModel):
    """Temporal analysis response model."""
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Trading symbol",
        example="NQ"
    )
    
    analysis_period_start: datetime = Field(
        description="Analysis period start",
        example="2024-01-01T00:00:00Z"
    )
    
    analysis_period_end: datetime = Field(
        description="Analysis period end",
        example="2024-12-31T23:59:59Z"
    )
    
    hourly_performance: Dict[int, Dict[str, Any]] = Field(
        description="Performance metrics by hour of day (0-23)",
        example={
            "9": {
                "total_trades": 25,
                "winning_trades": 16,
                "total_pnl": 1250.50,
                "average_pnl": 50.02,
                "win_rate": 64.0
            },
            "10": {
                "total_trades": 30,
                "winning_trades": 18,
                "total_pnl": 1500.75,
                "average_pnl": 50.03,
                "win_rate": 60.0
            }
        }
    )
    
    daily_performance: Dict[int, Dict[str, Any]] = Field(
        description="Performance metrics by day of week (0=Monday, 6=Sunday)",
        example={
            "0": {
                "total_trades": 35,
                "winning_trades": 22,
                "total_pnl": 1750.25,
                "average_pnl": 50.01,
                "win_rate": 62.86
            },
            "1": {
                "total_trades": 28,
                "winning_trades": 18,
                "total_pnl": 1400.50,
                "average_pnl": 50.02,
                "win_rate": 64.29
            }
        }
    )
    
    best_trading_hours: List[int] = Field(
        description="Hours with best performance (sorted by average P&L)",
        example=[10, 14, 9, 15]
    )
    
    best_trading_days: List[int] = Field(
        description="Days with best performance (sorted by average P&L)",
        example=[1, 3, 0, 2]
    )
    
    statistical_significance: Dict[str, Any] = Field(
        description="Statistical significance tests for temporal patterns",
        example={
            "hourly_anova": {
                "f_statistic": 2.45,
                "p_value": 0.032,
                "significant": True
            },
            "daily_anova": {
                "f_statistic": 1.87,
                "p_value": 0.089,
                "significant": False
            }
        }
    )


class AnalyticsRequest(BaseModel):
    """Analytics request parameters."""
    
    start_date: Optional[datetime] = Field(
        default=None,
        description="Analysis start date",
        example="2024-01-01T00:00:00Z"
    )
    
    end_date: Optional[datetime] = Field(
        default=None,
        description="Analysis end date",
        example="2024-12-31T23:59:59Z"
    )
    
    time_frame: Optional[TimeFrame] = Field(
        default=TimeFrame.DAILY,
        description="Time frame for analysis",
        example=TimeFrame.DAILY
    )
    
    include_statistics: bool = Field(
        default=True,
        description="Include statistical significance tests",
        example=True
    )
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate that end_date is after start_date."""
        if v and 'start_date' in values and values['start_date']:
            if v <= values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class MonteCarloRequest(BaseModel):
    """Monte Carlo simulation request."""
    
    account_name: str = Field(
        description="Account name for simulation",
        example="IPS_TM_10"
    )
    
    num_simulations: int = Field(
        default=10000,
        description="Number of simulation runs",
        example=10000,
        ge=1000,
        le=100000
    )
    
    time_horizon_days: int = Field(
        default=30,
        description="Simulation time horizon in days",
        example=30,
        ge=1,
        le=365
    )
    
    confidence_levels: List[float] = Field(
        default=[0.95, 0.99],
        description="Confidence levels for VaR calculation",
        example=[0.95, 0.99]
    )
    
    @validator('confidence_levels')
    def validate_confidence_levels(cls, v):
        """Validate confidence levels are between 0 and 1."""
        for level in v:
            if not 0 < level < 1:
                raise ValueError('Confidence levels must be between 0 and 1')
        return v


class MonteCarloResponse(BaseModel):
    """Monte Carlo simulation response."""
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    num_simulations: int = Field(
        description="Number of simulations run",
        example=10000
    )
    
    time_horizon_days: int = Field(
        description="Simulation time horizon",
        example=30
    )
    
    expected_return: float = Field(
        description="Expected return",
        example=1250.50
    )
    
    expected_volatility: float = Field(
        description="Expected volatility",
        example=850.25
    )
    
    var_estimates: Dict[str, float] = Field(
        description="Value at Risk estimates by confidence level",
        example={
            "95%": -2500.00,
            "99%": -4200.00
        }
    )
    
    expected_shortfall: Dict[str, float] = Field(
        description="Expected Shortfall (Conditional VaR) by confidence level",
        example={
            "95%": -3200.00,
            "99%": -5100.00
        }
    )
    
    percentiles: Dict[str, float] = Field(
        description="Return percentiles",
        example={
            "5%": -2500.00,
            "25%": -500.00,
            "50%": 1250.00,
            "75%": 3000.00,
            "95%": 5500.00
        }
    )
    
    probability_of_loss: float = Field(
        description="Probability of loss (0-100)",
        example=35.5,
        ge=0.0,
        le=100.0
    )
    
    simulation_metadata: Dict[str, Any] = Field(
        description="Simulation metadata and parameters",
        example={
            "historical_data_points": 1500,
            "simulation_start_date": "2024-01-01T00:00:00Z",
            "simulation_end_date": "2024-12-31T23:59:59Z",
            "convergence_achieved": True
        }
    )


class MonteCarloResultsResponse(BaseModel):
    """Monte Carlo simulation results response."""
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    simulations: int = Field(
        description="Number of simulations run",
        example=10000
    )
    
    time_horizon_days: int = Field(
        description="Time horizon in days",
        example=30
    )
    
    confidence_level: float = Field(
        description="Confidence level used",
        example=0.95
    )
    
    expected_return: float = Field(
        description="Expected return",
        example=1250.0
    )
    
    expected_volatility: float = Field(
        description="Expected volatility",
        example=850.0
    )
    
    value_at_risk: float = Field(
        description="Value at Risk",
        example=-2100.0
    )
    
    expected_shortfall: float = Field(
        description="Expected Shortfall",
        example=-2850.0
    )
    
    probability_of_profit: float = Field(
        description="Probability of profit",
        example=0.68
    )
    
    percentile_results: Dict[str, float] = Field(
        description="Percentile results",
        example={
            "5": -2850.0,
            "10": -2100.0,
            "25": -750.0,
            "50": 1250.0,
            "75": 3250.0,
            "90": 4850.0,
            "95": 6100.0
        }
    )
    
    max_simulated_loss: float = Field(
        description="Maximum simulated loss",
        example=-4250.0
    )
    
    max_simulated_gain: float = Field(
        description="Maximum simulated gain",
        example=8750.0
    )


class CorrelationAnalysisResponse(BaseModel):
    """Correlation analysis response."""
    
    accounts: List[str] = Field(
        description="List of accounts analyzed",
        example=["IPS_TM_10", "IPS_TM_13"]
    )
    
    period_start: datetime = Field(
        description="Analysis period start",
        example="2024-01-01T00:00:00Z"
    )
    
    period_end: datetime = Field(
        description="Analysis period end",
        example="2024-12-31T23:59:59Z"
    )
    
    correlation_matrix: Dict[str, Dict[str, float]] = Field(
        description="Correlation matrix between accounts",
        example={
            "IPS_TM_10": {"IPS_TM_10": 1.0, "IPS_TM_13": 0.35},
            "IPS_TM_13": {"IPS_TM_10": 0.35, "IPS_TM_13": 1.0}
        }
    )
    
    strongest_correlation: Dict[str, Any] = Field(
        description="Strongest correlation found",
        example={"accounts": ["IPS_TM_10", "IPS_TM_11"], "correlation": 0.75}
    )
    
    weakest_correlation: Dict[str, Any] = Field(
        description="Weakest correlation found",
        example={"accounts": ["IPS_TM_10", "IPS_TM_13"], "correlation": 0.15}
    )
    
    diversification_score: float = Field(
        description="Portfolio diversification score (0-1)",
        example=0.68,
        ge=0.0,
        le=1.0
    )
    
    portfolio_risk_reduction: float = Field(
        description="Risk reduction from diversification",
        example=0.23,
        ge=0.0,
        le=1.0
    )


class PerformanceMetricsResponse(BaseModel):
    """Enhanced performance metrics response model."""
    
    account_name: str = Field(description="Account name")
    symbol: str = Field(description="Trading symbol")
    period_start: datetime = Field(description="Analysis period start")
    period_end: datetime = Field(description="Analysis period end")
    total_return: float = Field(description="Total return amount")
    total_trades: int = Field(description="Total number of trades")
    winning_trades: int = Field(description="Number of winning trades")
    losing_trades: int = Field(description="Number of losing trades")
    win_rate: float = Field(description="Win rate percentage", ge=0.0, le=100.0)
    average_win: float = Field(description="Average winning trade amount")
    average_loss: float = Field(description="Average losing trade amount")
    profit_factor: float = Field(description="Profit factor")
    max_drawdown: float = Field(description="Maximum drawdown amount")
    sharpe_ratio: Optional[float] = Field(description="Sharpe ratio")
    volatility: float = Field(description="Return volatility")
    largest_win: float = Field(description="Largest winning trade")
    largest_loss: float = Field(description="Largest losing trade")
    average_trade_duration: Optional[float] = Field(None, description="Average duration in minutes")
    total_commission: Optional[float] = Field(0.0, description="Total commission")
    net_profit: Optional[float] = Field(None, description="Net profit")


class TemporalAnalysisResponse(BaseModel):
    """Enhanced temporal analysis response model."""
    
    account_name: str
    symbol: str
    period_start: datetime
    period_end: datetime
    hourly_performance: Dict[str, Dict[str, Any]]
    daily_performance: Dict[str, Dict[str, Any]]
    best_trading_hours: List[int]
    best_trading_days: List[int]
    statistical_significance: Dict[str, Any]


class EdgeDiscoveryResponse(BaseModel):
    """Edge discovery response model."""
    symbol: str
    edges: List[Dict[str, Any]]


class WalkForwardValidationResponse(BaseModel):
    """Walk-forward validation response model."""
    symbol: str
    logic: str
    equity_curve: List[Dict[str, Any]]
    metrics: Dict[str, Any]
