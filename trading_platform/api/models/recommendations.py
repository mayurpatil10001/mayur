"""
Pydantic models for recommendation-related API endpoints.

This module contains request/response models for trading recommendation endpoints.

Requirements: 10.1, 10.4
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum


class RecommendationAction(str, Enum):
    """Recommendation action types."""
    TRADE = "TRADE"
    AVOID = "AVOID"
    WAIT = "WAIT"


class StrategyType(str, Enum):
    """Trading strategy types."""
    STATISTICAL = "STATISTICAL"
    MACHINE_LEARNING = "MACHINE_LEARNING"
    MONTE_CARLO = "MONTE_CARLO"
    COMBINED = "COMBINED"


class RiskTolerance(str, Enum):
    """Risk tolerance levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class TradingRecommendationResponse(BaseModel):
    """Trading recommendation response model."""
    
    timestamp: datetime = Field(
        description="Recommendation timestamp",
        example="2024-01-01T09:30:00Z"
    )
    
    account_name: str = Field(
        description="Recommended account",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Recommended symbol",
        example="NQ"
    )
    
    recommended_action: RecommendationAction = Field(
        description="Recommended action",
        example=RecommendationAction.TRADE
    )
    
    confidence_score: float = Field(
        description="Confidence score (0-100)",
        example=85.5,
        ge=0.0,
        le=100.0
    )
    
    expected_return: float = Field(
        description="Expected return amount",
        example=125.50
    )
    
    expected_risk: float = Field(
        description="Expected risk (standard deviation)",
        example=75.25
    )
    
    reasoning: str = Field(
        description="Human-readable reasoning for recommendation",
        example="Historical data shows 68% win rate at this time for NQ on Mondays"
    )
    
    hour_of_day: int = Field(
        description="Hour of day for recommendation",
        example=9,
        ge=0,
        le=23
    )
    
    day_of_week: int = Field(
        description="Day of week for recommendation (0=Monday)",
        example=0,
        ge=0,
        le=6
    )
    
    historical_win_rate: float = Field(
        description="Historical win rate for this time/account/symbol",
        example=68.5,
        ge=0.0,
        le=100.0
    )
    
    avg_profit_this_time: float = Field(
        description="Average profit for this time pattern",
        example=145.75
    )
    
    strategy_used: StrategyType = Field(
        description="Strategy used for recommendation",
        example=StrategyType.COMBINED
    )
    
    risk_metrics: Dict[str, float] = Field(
        description="Risk metrics for the recommendation",
        example={
            "var_95": -250.00,
            "max_drawdown_risk": -180.50,
            "volatility": 0.15
        }
    )


class RecommendationRequest(BaseModel):
    """Recommendation request parameters."""
    
    target_time: Optional[datetime] = Field(
        default=None,
        description="Target time for recommendation (defaults to current time)",
        example="2024-01-01T09:30:00Z"
    )
    
    account_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter recommendations to specific accounts",
        example=["IPS_TM_10", "IPS_TM_13"]
    )
    
    symbol_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter recommendations to specific symbols",
        example=["NQ", "FDAX"]
    )
    
    strategy: Optional[StrategyType] = Field(
        default=StrategyType.COMBINED,
        description="Strategy to use for recommendations",
        example=StrategyType.COMBINED
    )
    
    risk_tolerance: RiskTolerance = Field(
        default=RiskTolerance.MEDIUM,
        description="Risk tolerance level",
        example=RiskTolerance.MEDIUM
    )
    
    min_confidence: float = Field(
        default=60.0,
        description="Minimum confidence score for recommendations",
        example=60.0,
        ge=0.0,
        le=100.0
    )


class StrategyComparisonResponse(BaseModel):
    """Strategy comparison response model."""
    
    comparison_period_start: datetime = Field(
        description="Comparison period start",
        example="2024-01-01T00:00:00Z"
    )
    
    comparison_period_end: datetime = Field(
        description="Comparison period end",
        example="2024-12-31T23:59:59Z"
    )
    
    strategies: Dict[str, Dict[str, Any]] = Field(
        description="Strategy performance comparison",
        example={
            "STATISTICAL": {
                "total_recommendations": 150,
                "successful_recommendations": 95,
                "success_rate": 63.33,
                "average_return": 125.50,
                "total_return": 11922.50,
                "sharpe_ratio": 1.25,
                "max_drawdown": -850.00
            },
            "MACHINE_LEARNING": {
                "total_recommendations": 142,
                "successful_recommendations": 98,
                "success_rate": 69.01,
                "average_return": 135.75,
                "total_return": 13275.25,
                "sharpe_ratio": 1.45,
                "max_drawdown": -720.00
            },
            "MONTE_CARLO": {
                "total_recommendations": 138,
                "successful_recommendations": 89,
                "success_rate": 64.49,
                "average_return": 142.25,
                "total_return": 12650.75,
                "sharpe_ratio": 1.35,
                "max_drawdown": -950.00
            }
        }
    )
    
    best_strategy: StrategyType = Field(
        description="Best performing strategy",
        example=StrategyType.MACHINE_LEARNING
    )
    
    statistical_tests: Dict[str, Any] = Field(
        description="Statistical significance tests between strategies",
        example={
            "ml_vs_statistical": {
                "t_statistic": 2.15,
                "p_value": 0.032,
                "significant": True
            },
            "ml_vs_monte_carlo": {
                "t_statistic": 1.87,
                "p_value": 0.061,
                "significant": False
            }
        }
    )
    
    recommendation: str = Field(
        description="Strategy recommendation based on analysis",
        example="Machine Learning strategy shows statistically significant better performance"
    )


class BacktestRequest(BaseModel):
    """Backtest request parameters."""
    
    strategy: StrategyType = Field(
        description="Strategy to backtest",
        example=StrategyType.MACHINE_LEARNING
    )
    
    start_date: datetime = Field(
        description="Backtest start date",
        example="2024-01-01T00:00:00Z"
    )
    
    end_date: datetime = Field(
        description="Backtest end date",
        example="2024-12-31T23:59:59Z"
    )
    
    account_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter backtest to specific accounts",
        example=["IPS_TM_10", "IPS_TM_13"]
    )
    
    symbol_filter: Optional[List[str]] = Field(
        default=None,
        description="Filter backtest to specific symbols",
        example=["NQ", "FDAX"]
    )
    
    risk_tolerance: RiskTolerance = Field(
        default=RiskTolerance.MEDIUM,
        description="Risk tolerance for backtest",
        example=RiskTolerance.MEDIUM
    )
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        """Validate that end_date is after start_date."""
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class BacktestResponse(BaseModel):
    """Backtest response model."""
    
    strategy: StrategyType = Field(
        description="Strategy backtested",
        example=StrategyType.MACHINE_LEARNING
    )
    
    backtest_period_start: datetime = Field(
        description="Backtest period start",
        example="2024-01-01T00:00:00Z"
    )
    
    backtest_period_end: datetime = Field(
        description="Backtest period end",
        example="2024-12-31T23:59:59Z"
    )
    
    total_recommendations: int = Field(
        description="Total recommendations generated",
        example=150
    )
    
    successful_recommendations: int = Field(
        description="Number of successful recommendations",
        example=98
    )
    
    success_rate: float = Field(
        description="Success rate percentage",
        example=65.33,
        ge=0.0,
        le=100.0
    )
    
    total_return: float = Field(
        description="Total return from following recommendations",
        example=12500.75
    )
    
    average_return_per_recommendation: float = Field(
        description="Average return per recommendation",
        example=83.34
    )
    
    sharpe_ratio: float = Field(
        description="Sharpe ratio of recommendation returns",
        example=1.45
    )
    
    max_drawdown: float = Field(
        description="Maximum drawdown",
        example=-850.00
    )
    
    volatility: float = Field(
        description="Return volatility",
        example=0.18
    )
    
    monthly_returns: Dict[str, float] = Field(
        description="Monthly returns breakdown",
        example={
            "2024-01": 1250.50,
            "2024-02": 980.25,
            "2024-03": 1450.75
        }
    )
    
    confidence_distribution: Dict[str, int] = Field(
        description="Distribution of recommendations by confidence level",
        example={
            "60-70": 25,
            "70-80": 45,
            "80-90": 55,
            "90-100": 25
        }
    )


class TradingRecommendationResponse(BaseModel):
    """Enhanced trading recommendation response model."""
    
    timestamp: datetime = Field(
        description="Recommendation timestamp",
        example="2024-01-01T09:30:00Z"
    )
    
    account_name: str = Field(
        description="Recommended account",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Recommended symbol",
        example="NQ"
    )
    
    recommended_action: RecommendationAction = Field(
        description="Recommended action",
        example=RecommendationAction.TRADE
    )
    
    confidence_score: float = Field(
        description="Confidence score (0-1)",
        example=0.855,
        ge=0.0,
        le=1.0
    )
    
    expected_return: float = Field(
        description="Expected return amount",
        example=125.50
    )
    
    expected_risk: float = Field(
        description="Expected risk (standard deviation)",
        example=75.25
    )
    
    reasoning: str = Field(
        description="Human-readable reasoning for recommendation",
        example="Historical data shows 68% win rate at this time for NQ on Mondays"
    )
    
    hour_of_day: int = Field(
        description="Hour of day for recommendation",
        example=9,
        ge=0,
        le=23
    )
    
    day_of_week: int = Field(
        description="Day of week for recommendation (0=Monday)",
        example=0,
        ge=0,
        le=6
    )
    
    historical_win_rate: float = Field(
        description="Historical win rate for this time/account/symbol",
        example=0.685,
        ge=0.0,
        le=1.0
    )
    
    avg_profit_this_time: float = Field(
        description="Average profit for this time pattern",
        example=145.75
    )
    
    strategy_used: str = Field(
        description="Strategy used for recommendation",
        example="statistical_temporal"
    )
    
    risk_score: float = Field(
        description="Risk score (0-1, higher is riskier)",
        example=0.25,
        ge=0.0,
        le=1.0
    )
    
    market_conditions: str = Field(
        description="Current market conditions assessment",
        example="favorable"
    )


class RecommendationRequest(BaseModel):
    """Enhanced recommendation request parameters."""
    
    account_name: str = Field(
        description="Account name for recommendation",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Symbol for recommendation",
        example="NQ"
    )
    
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Target timestamp for recommendation (defaults to current time)",
        example="2024-01-01T09:30:00Z"
    )
    
    strategy: Optional[str] = Field(
        default=None,
        description="Specific strategy to use",
        example="statistical_temporal"
    )
    
    risk_tolerance: Optional[str] = Field(
        default="medium",
        description="Risk tolerance level",
        example="medium"
    )


class StrategyComparisonResponse(BaseModel):
    """Enhanced strategy comparison response model."""
    
    comparison_period_start: datetime = Field(
        description="Comparison period start",
        example="2024-01-01T00:00:00Z"
    )
    
    comparison_period_end: datetime = Field(
        description="Comparison period end",
        example="2024-12-31T23:59:59Z"
    )
    
    account_name: str = Field(
        description="Account name for comparison",
        example="IPS_TM_10"
    )
    
    strategies_compared: List[str] = Field(
        description="List of strategies compared",
        example=["statistical_temporal", "ml_enhanced", "monte_carlo_optimized"]
    )
    
    strategy_performance: Dict[str, Dict[str, Any]] = Field(
        description="Performance metrics for each strategy",
        example={
            "statistical_temporal": {
                "total_recommendations": 150,
                "successful_recommendations": 98,
                "success_rate": 0.653,
                "average_return": 125.50,
                "total_return": 12285.00,
                "sharpe_ratio": 1.15,
                "max_drawdown": -850.00
            }
        }
    )
    
    best_strategy: str = Field(
        description="Best performing strategy",
        example="monte_carlo_optimized"
    )
    
    statistical_significance: Dict[str, Any] = Field(
        description="Statistical significance tests",
        example={
            "anova_f_statistic": 3.45,
            "anova_p_value": 0.032,
            "significant_differences": True
        }
    )
    
    recommendation: str = Field(
        description="Strategy recommendation",
        example="Use monte_carlo_optimized strategy for best risk-adjusted returns"
    )


class RecommendationHistoryResponse(BaseModel):
    """Recommendation history response model."""
    
    recommendation_id: str = Field(
        description="Unique recommendation ID",
        example="rec_001"
    )
    
    timestamp: datetime = Field(
        description="Recommendation timestamp",
        example="2024-01-01T09:30:00Z"
    )
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    symbol: str = Field(
        description="Symbol",
        example="NQ"
    )
    
    recommended_action: RecommendationAction = Field(
        description="Recommended action",
        example=RecommendationAction.TRADE
    )
    
    confidence_score: float = Field(
        description="Confidence score",
        example=0.75,
        ge=0.0,
        le=1.0
    )
    
    expected_return: float = Field(
        description="Expected return",
        example=125.50
    )
    
    actual_return: Optional[float] = Field(
        description="Actual return (if trade was executed)",
        example=135.25
    )
    
    strategy_used: str = Field(
        description="Strategy used",
        example="statistical_temporal"
    )
    
    outcome: str = Field(
        description="Recommendation outcome",
        example="successful"
    )
    
    accuracy_score: float = Field(
        description="Accuracy score of the recommendation",
        example=0.92,
        ge=0.0,
        le=1.0
    )


class BacktestResultsResponse(BaseModel):
    """Backtest results response model."""
    
    strategy_name: str = Field(
        description="Strategy name",
        example="statistical_temporal"
    )
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    backtest_period_start: datetime = Field(
        description="Backtest period start",
        example="2024-01-01T00:00:00Z"
    )
    
    backtest_period_end: datetime = Field(
        description="Backtest period end",
        example="2024-12-31T23:59:59Z"
    )
    
    total_recommendations: int = Field(
        description="Total recommendations",
        example=250
    )
    
    successful_recommendations: int = Field(
        description="Successful recommendations",
        example=165
    )
    
    failed_recommendations: int = Field(
        description="Failed recommendations",
        example=85
    )
    
    success_rate: float = Field(
        description="Success rate",
        example=0.66,
        ge=0.0,
        le=1.0
    )
    
    total_return: float = Field(
        description="Total return",
        example=15750.50
    )
    
    average_return_per_recommendation: float = Field(
        description="Average return per recommendation",
        example=63.00
    )
    
    sharpe_ratio: float = Field(
        description="Sharpe ratio",
        example=1.25
    )
    
    max_drawdown: float = Field(
        description="Maximum drawdown",
        example=-1250.00
    )
    
    volatility: float = Field(
        description="Return volatility",
        example=0.18
    )
    
    best_month: Dict[str, Any] = Field(
        description="Best performing month",
        example={"month": "March 2024", "return": 2850.00}
    )
    
    worst_month: Dict[str, Any] = Field(
        description="Worst performing month",
        example={"month": "August 2024", "return": -950.00}
    )
    
    monthly_returns: Dict[str, float] = Field(
        description="Monthly returns",
        example={
            "2024-01": 1250.00,
            "2024-02": 1850.50,
            "2024-03": 2850.00
        }
    )
    
    confidence_analysis: Dict[str, float] = Field(
        description="Analysis by confidence level",
        example={
            "high_confidence_success_rate": 0.78,
            "medium_confidence_success_rate": 0.65,
            "low_confidence_success_rate": 0.52
        }
    )