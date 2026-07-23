"""
Pydantic models for time-bin analytics API endpoints.

This module contains request/response models for time-bin specific analytics endpoints.

Requirements: 1.1, 1.6, 4.4, 10.1
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple, Union
from pydantic import BaseModel, Field, validator
from enum import Enum


class TimeBinRequest(BaseModel):
    """Request model for time-bin analysis."""
    
    account_name: str = Field(
        description="Account name for analysis",
        example="IPS_TM_10"
    )
    
    hour: int = Field(
        description="Hour of day (0-23)",
        example=9,
        ge=0,
        le=23
    )
    
    minute_bin: int = Field(
        description="Minute bin (0 or 30)",
        example=30
    )
    
    day_of_week: Optional[int] = Field(
        default=None,
        description="Day of week (0=Monday, 6=Sunday), None for all days",
        example=1,
        ge=0,
        le=6
    )
    
    @validator('minute_bin')
    def validate_minute_bin(cls, v):
        """Validate minute bin is 0 or 30."""
        if v not in [0, 30]:
            raise ValueError('Minute bin must be 0 or 30')
        return v


class TimeBinMetricsResponse(BaseModel):
    """Response model for time-bin performance metrics."""
    
    time_bin_id: str = Field(
        description="Time bin identifier",
        example="IPS_TM_10_09:30"
    )
    
    account_name: str = Field(
        description="Account name",
        example="IPS_TM_10"
    )
    
    hour: int = Field(
        description="Hour of day",
        example=9
    )
    
    minute_bin: int = Field(
        description="Minute bin",
        example=30
    )
    
    day_of_week: Optional[int] = Field(
        description="Day of week filter",
        example=1
    )
    
    # Basic performance metrics
    total_trades: int = Field(
        description="Total number of trades",
        example=45
    )
    
    winning_trades: int = Field(
        description="Number of winning trades",
        example=28
    )
    
    losing_trades: int = Field(
        description="Number of losing trades",
        example=17
    )
    
    win_rate: float = Field(
        description="Win rate percentage (0-100)",
        example=62.22,
        ge=0.0,
        le=100.0
    )
    
    total_pnl: float = Field(
        description="Total profit/loss",
        example=2250.50
    )
    
    average_pnl: float = Field(
        description="Average profit/loss per trade",
        example=50.01
    )
    
    average_win: float = Field(
        description="Average winning trade",
        example=125.75
    )
    
    average_loss: float = Field(
        description="Average losing trade",
        example=-85.25
    )
    
    # Risk metrics
    max_drawdown: float = Field(
        description="Maximum drawdown",
        example=-450.00
    )
    
    volatility: float = Field(
        description="Return volatility",
        example=95.50
    )
    
    profit_factor: float = Field(
        description="Profit factor (gross profit / gross loss)",
        example=1.85
    )
    
    largest_win: float = Field(
        description="Largest winning trade",
        example=275.00
    )
    
    largest_loss: float = Field(
        description="Largest losing trade",
        example=-185.50
    )
    
    # Risk-adjusted ratios
    sharpe_ratio: Optional[float] = Field(
        description="Sharpe ratio",
        example=1.25
    )
    
    calmar_ratio: Optional[float] = Field(
        description="Calmar ratio",
        example=2.15
    )
    
    sortino_ratio: Optional[float] = Field(
        description="Sortino ratio",
        example=1.85
    )
    
    # Statistical significance
    confidence_interval_95: Optional[Tuple[float, float]] = Field(
        description="95% confidence interval for average P&L",
        example=[35.25, 64.77]
    )

    p_value_vs_random: Optional[float] = Field(
        description="Raw p-value testing against random trading (NOT corrected for multiple comparisons)",
        example=0.032
    )

    statistical_significance: bool = Field(
        description="Raw significance gate: p_value_vs_random < 0.05. Kept for transparency; use bh_significant for decisions.",
        example=True
    )

    # Benjamini-Hochberg FDR-corrected significance
    # Populated by the recommendations endpoint; None for single-bin lookups.
    adjusted_p_value: Optional[float] = Field(
        default=None,
        description="BH-adjusted p-value (q-value). None when slot was analyzed in isolation.",
        example=0.041
    )

    bh_significant: Optional[bool] = Field(
        default=None,
        description="True only when adjusted_p_value <= 0.05 (FDR-corrected). Use this — not statistical_significance — as the recommendation gate.",
        example=True
    )

    minimum_sample_size_met: bool = Field(
        description="Whether minimum sample size is met for statistical tests",
        example=True
    )
    
    # Additional derived metrics
    expectancy: float = Field(
        description="Expected value per trade",
        example=52.15
    )
    
    recovery_factor: float = Field(
        description="Recovery factor (total return / max drawdown)",
        example=5.0
    )


class SignificanceTestResponse(BaseModel):
    """Response model for statistical significance tests."""
    
    test_name: str = Field(
        description="Name of the statistical test",
        example="One-sample t-test vs zero"
    )
    
    p_value: float = Field(
        description="P-value of the test",
        example=0.032
    )
    
    is_significant: bool = Field(
        description="Whether the result is statistically significant",
        example=True
    )
    
    confidence_level: float = Field(
        description="Confidence level used",
        example=0.95
    )
    
    test_statistic: float = Field(
        description="Test statistic value",
        example=2.45
    )
    
    critical_value: float = Field(
        description="Critical value for the test",
        example=2.021
    )
    
    interpretation: str = Field(
        description="Interpretation of the test result",
        example="Tests if average P&L is significantly different from zero (random trading)"
    )


class TimeBinAnalysisResponse(BaseModel):
    """Complete time-bin analysis response."""
    
    metrics: TimeBinMetricsResponse = Field(
        description="Performance metrics for the time bin"
    )
    
    significance_tests: List[SignificanceTestResponse] = Field(
        description="Statistical significance test results"
    )
    
    analysis_timestamp: datetime = Field(
        description="When the analysis was performed",
        default_factory=datetime.now
    )
    
    data_period: Dict[str, Any] = Field(
        description="Information about the data period analyzed",
        example={
            "earliest_trade": "2024-01-15T09:30:00Z",
            "latest_trade": "2024-12-15T09:45:00Z",
            "total_trading_days": 245
        }
    )


class TimeBinComparisonRequest(BaseModel):
    """Request model for comparing multiple time bins."""
    
    time_bins: List[TimeBinRequest] = Field(
        description="List of time bins to compare",
        min_items=2,
        max_items=10
    )
    
    include_statistical_tests: bool = Field(
        default=True,
        description="Include statistical comparison tests"
    )
    
    sort_by: str = Field(
        default="average_pnl",
        description="Metric to sort results by",
        example="average_pnl"
    )
    
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order",
        example="desc"
    )


class TimeBinComparisonResponse(BaseModel):
    """Response model for time-bin comparison."""
    
    time_bins: List[TimeBinAnalysisResponse] = Field(
        description="Analysis results for each time bin"
    )
    
    ranking: List[Dict[str, Any]] = Field(
        description="Ranking of time bins by selected metric",
        example=[
            {"rank": 1, "time_bin_id": "IPS_TM_10_09:30", "value": 65.25},
            {"rank": 2, "time_bin_id": "IPS_TM_10_14:00", "value": 52.10}
        ]
    )
    
    statistical_comparisons: Optional[List[Dict[str, Any]]] = Field(
        description="Pairwise statistical comparisons between time bins"
    )
    
    best_time_bin: Dict[str, Any] = Field(
        description="Information about the best performing time bin",
        example={
            "time_bin_id": "IPS_TM_10_09:30",
            "metric_value": 65.25,
            "statistical_significance": True
        }
    )


class AccountRecommendationsRequest(BaseModel):
    """Request model for account recommendations."""
    
    account_name: str = Field(
        description="Account name to analyze",
        example="IPS_TM_10"
    )
    
    min_trades: int = Field(
        default=30,
        description="Minimum number of trades required for recommendation",
        example=30,
        ge=10
    )
    
    min_win_rate: float = Field(
        default=50.0,
        description="Minimum win rate percentage for recommendation",
        example=55.0,
        ge=0.0,
        le=100.0
    )
    
    min_average_pnl: float = Field(
        default=0.0,
        description="Minimum average P&L for recommendation",
        example=25.0
    )
    
    include_statistical_significance: bool = Field(
        default=True,
        description="Only recommend statistically significant time bins"
    )
    
    max_recommendations: int = Field(
        default=10,
        description="Maximum number of recommendations to return",
        example=5,
        ge=1,
        le=50
    )


class TimeBinRecommendation(BaseModel):
    """Individual time-bin recommendation."""
    
    rank: int = Field(
        description="Recommendation rank (1 = best)",
        example=1
    )
    
    time_bin_id: str = Field(
        description="Time bin identifier",
        example="IPS_TM_10_09:30"
    )
    
    hour: int = Field(
        description="Hour of day",
        example=9
    )
    
    minute_bin: int = Field(
        description="Minute bin",
        example=30
    )
    
    day_of_week: Optional[int] = Field(
        description="Day of week (if specific)",
        example=1
    )
    
    score: float = Field(
        description="Recommendation score",
        example=85.5
    )
    
    key_metrics: Dict[str, float] = Field(
        description="Key performance metrics",
        example={
            "average_pnl": 65.25,
            "win_rate": 62.5,
            "total_trades": 45,
            "sharpe_ratio": 1.25
        }
    )
    
    confidence_level: str = Field(
        description="Confidence level in recommendation",
        example="High"
    )
    
    risk_assessment: str = Field(
        description="Risk level assessment",
        example="Medium"
    )
    
    recommendation_reason: str = Field(
        description="Explanation for why this time bin is recommended",
        example="Strong average P&L with good win rate and statistical significance"
    )


class AccountRecommendationsResponse(BaseModel):
    """Response model for account recommendations."""
    
    account_name: str = Field(
        description="Account name analyzed",
        example="IPS_TM_10"
    )
    
    recommendations: List[TimeBinRecommendation] = Field(
        description="List of recommended time bins"
    )
    
    analysis_summary: Dict[str, Any] = Field(
        description="Summary of the analysis",
        example={
            "total_time_bins_analyzed": 48,
            "time_bins_meeting_criteria": 12,
            "best_overall_metric": "average_pnl",
            "analysis_period_days": 365
        }
    )
    
    filters_applied: Dict[str, Any] = Field(
        description="Filters that were applied",
        example={
            "min_trades": 30,
            "min_win_rate": 55.0,
            "min_average_pnl": 25.0,
            "statistical_significance_required": True
        }
    )
    
    warnings: List[str] = Field(
        description="Any warnings about the analysis",
        example=["Some time bins had insufficient data for statistical significance testing"]
    )

    # --- Walk-Forward Validation Gating (Task 3) ---
    pending_validation: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Time bins meeting statistical criteria but awaiting Walk-Forward Analysis (WFA) execution."
    )

    failed_wfa: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Time bins meeting statistical criteria but failing Walk-Forward out-of-sample validation."
    )


class InsufficientDataError(BaseModel):
    """Error response for insufficient trade data scenarios."""
    
    error_type: str = Field(
        description="Type of error",
        example="INSUFFICIENT_DATA"
    )
    
    message: str = Field(
        description="Error message",
        example="Insufficient trade data for reliable analysis"
    )
    
    details: Dict[str, Any] = Field(
        description="Additional error details",
        example={
            "trades_found": 5,
            "minimum_required": 30,
            "time_bin": "IPS_TM_10_09:30",
            "suggestion": "Try a different time window or account with more trading history"
        }
    )
    
    recommendations: List[str] = Field(
        description="Recommendations to resolve the issue",
        example=[
            "Increase the analysis time period",
            "Try a broader time window (e.g., hourly instead of 30-minute bins)",
            "Consider analyzing a different account with more trading activity"
        ]
    )


# Market Correlation and Benchmark Analysis Models

class BetaCoefficientsResponse(BaseModel):
    """Response model for beta coefficient analysis."""
    
    spy_beta: float = Field(
        description="Beta coefficient relative to SPY",
        example=0.65
    )
    
    qqq_beta: float = Field(
        description="Beta coefficient relative to QQQ", 
        example=0.58
    )
    
    spy_r_squared: float = Field(
        description="R-squared for SPY regression",
        example=0.42
    )
    
    qqq_r_squared: float = Field(
        description="R-squared for QQQ regression",
        example=0.38
    )
    
    spy_correlation: float = Field(
        description="Correlation coefficient with SPY",
        example=0.65
    )
    
    qqq_correlation: float = Field(
        description="Correlation coefficient with QQQ",
        example=0.62
    )
    
    sample_size: int = Field(
        description="Number of observations used",
        example=120
    )
    
    calculation_period_days: int = Field(
        description="Period over which beta was calculated",
        example=180
    )


class AlphaMetricsResponse(BaseModel):
    """Response model for alpha metrics analysis."""
    
    spy_alpha_annual: float = Field(
        description="Annualized alpha relative to SPY",
        example=0.08
    )
    
    qqq_alpha_annual: float = Field(
        description="Annualized alpha relative to QQQ",
        example=0.06
    )
    
    spy_alpha_daily: float = Field(
        description="Daily alpha relative to SPY",
        example=0.0003
    )
    
    qqq_alpha_daily: float = Field(
        description="Daily alpha relative to QQQ",
        example=0.0002
    )
    
    jensen_alpha: float = Field(
        description="Jensen's alpha (risk-adjusted)",
        example=0.0004
    )
    
    information_ratio_spy: float = Field(
        description="Information ratio relative to SPY",
        example=1.25
    )
    
    information_ratio_qqq: float = Field(
        description="Information ratio relative to QQQ",
        example=1.15
    )
    
    tracking_error_spy: float = Field(
        description="Tracking error relative to SPY",
        example=0.06
    )
    
    tracking_error_qqq: float = Field(
        description="Tracking error relative to QQQ",
        example=0.05
    )
    
    treynor_ratio: float = Field(
        description="Treynor ratio (excess return per unit beta)",
        example=0.12
    )


class MarketNeutralityResponse(BaseModel):
    """Response model for market neutrality test."""
    
    is_market_neutral_spy: bool = Field(
        description="Whether strategy is neutral to SPY",
        example=True
    )
    
    is_market_neutral_qqq: bool = Field(
        description="Whether strategy is neutral to QQQ",
        example=True
    )
    
    spy_correlation_p_value: float = Field(
        description="P-value for SPY correlation test",
        example=0.12
    )
    
    qqq_correlation_p_value: float = Field(
        description="P-value for QQQ correlation test",
        example=0.08
    )
    
    spy_beta_p_value: float = Field(
        description="P-value for SPY beta significance test",
        example=0.15
    )
    
    qqq_beta_p_value: float = Field(
        description="P-value for QQQ beta significance test",
        example=0.11
    )
    
    market_neutrality_score: float = Field(
        description="Overall market neutrality score (0-1)",
        example=0.82
    )
    
    independence_test_statistic: float = Field(
        description="Independence test statistic",
        example=1.25
    )
    
    independence_p_value: float = Field(
        description="P-value for independence test",
        example=0.21
    )


class CorrelationStabilityResponse(BaseModel):
    """Response model for correlation stability analysis."""
    
    rolling_correlations_spy: List[float] = Field(
        description="Rolling correlation values with SPY",
        example=[0.65, 0.58, 0.72, 0.61]
    )
    
    rolling_correlations_qqq: List[float] = Field(
        description="Rolling correlation values with QQQ",
        example=[0.62, 0.55, 0.69, 0.58]
    )
    
    correlation_dates: List[datetime] = Field(
        description="Dates for rolling correlations",
        example=["2024-01-30", "2024-02-29", "2024-03-31"]
    )
    
    correlation_volatility_spy: float = Field(
        description="Volatility of SPY correlations",
        example=0.08
    )
    
    correlation_volatility_qqq: float = Field(
        description="Volatility of QQQ correlations",
        example=0.07
    )
    
    correlation_trend_spy: float = Field(
        description="Trend in SPY correlations over time",
        example=-0.02
    )
    
    correlation_trend_qqq: float = Field(
        description="Trend in QQQ correlations over time",
        example=-0.015
    )
    
    stability_score_spy: float = Field(
        description="Stability score for SPY correlations (0-1)",
        example=0.78
    )
    
    stability_score_qqq: float = Field(
        description="Stability score for QQQ correlations (0-1)",
        example=0.81
    )
    
    regime_correlation_spy: Dict[str, float] = Field(
        description="SPY correlations by market regime",
        example={"Low": 0.45, "Medium": 0.65, "High": 0.85}
    )
    
    regime_correlation_qqq: Dict[str, float] = Field(
        description="QQQ correlations by market regime",
        example={"Low": 0.42, "Medium": 0.62, "High": 0.82}
    )


class MarketCorrelationResponse(BaseModel):
    """Complete market correlation analysis response."""
    
    beta_coefficients: BetaCoefficientsResponse = Field(
        description="Beta coefficient analysis"
    )
    
    correlation_stability: CorrelationStabilityResponse = Field(
        description="Correlation stability over time"
    )
    
    analysis_period: Dict[str, Any] = Field(
        description="Analysis period information",
        example={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30", 
            "total_days": 180,
            "trading_days": 126
        }
    )
    
    analysis_timestamp: datetime = Field(
        description="When analysis was performed",
        default_factory=datetime.now
    )


class BenchmarkComparisonResponse(BaseModel):
    """Complete benchmark comparison analysis response."""
    
    beta_coefficients: BetaCoefficientsResponse = Field(
        description="Beta coefficient analysis"
    )
    
    alpha_metrics: AlphaMetricsResponse = Field(
        description="Alpha and risk-adjusted metrics"
    )
    
    market_neutrality: MarketNeutralityResponse = Field(
        description="Market neutrality test results"
    )
    
    correlation_stability: CorrelationStabilityResponse = Field(
        description="Correlation stability analysis"
    )
    
    analysis_period: Dict[str, Any] = Field(
        description="Analysis period information"
    )
    
    analysis_timestamp: datetime = Field(
        description="When analysis was performed",
        default_factory=datetime.now
    )


class VixRegimePerformanceResponse(BaseModel):
    """Response model for VIX regime-specific performance."""
    
    regime: str = Field(
        description="VIX volatility regime",
        example="Medium"
    )
    
    total_trades: int = Field(
        description="Number of trades in this regime",
        example=45
    )
    
    win_rate: float = Field(
        description="Win rate in this regime",
        example=0.58
    )
    
    avg_pnl: float = Field(
        description="Average P&L per trade in regime",
        example=125.50
    )
    
    total_pnl: float = Field(
        description="Total P&L in regime",
        example=5647.50
    )
    
    profit_factor: float = Field(
        description="Profit factor in regime",
        example=1.35
    )
    
    sharpe_ratio: Optional[float] = Field(
        description="Sharpe-like ratio in regime",
        example=1.12
    )
    
    avg_vix_level: float = Field(
        description="Average VIX level in regime",
        example=18.5
    )


class RegimeTransitionResponse(BaseModel):
    """Response model for regime transition analysis."""
    
    transition_date: datetime = Field(
        description="Date of regime transition"
    )
    
    from_regime: str = Field(
        description="Previous regime",
        example="Low"
    )
    
    to_regime: str = Field(
        description="New regime",
        example="Medium"
    )
    
    trigger_vix_level: float = Field(
        description="VIX level that triggered transition",
        example=15.2
    )
    
    days_in_previous_regime: int = Field(
        description="Days spent in previous regime",
        example=12
    )


class RegimeAnalysisResponse(BaseModel):
    """Complete regime-specific performance analysis."""
    
    regime_performance: List[VixRegimePerformanceResponse] = Field(
        description="Performance by VIX regime"
    )
    
    regime_transitions: List[RegimeTransitionResponse] = Field(
        description="Detected regime transitions"
    )
    
    regime_summary: Dict[str, Any] = Field(
        description="Summary of regime analysis",
        example={
            "total_regimes_found": 3,
            "most_profitable_regime": "Low",
            "most_active_regime": "Medium",
            "regime_stability_score": 0.75
        }
    )
    
    analysis_period: Dict[str, Any] = Field(
        description="Analysis period information"
    )
    
    analysis_timestamp: datetime = Field(
        description="When analysis was performed",
        default_factory=datetime.now
    )


class MarketDataSyncRequest(BaseModel):
    """Request model for market data synchronization."""
    
    symbols: List[str] = Field(
        description="Symbols to sync (SPY, QQQ, VIX)",
        example=["SPY", "QQQ", "VIX"]
    )
    
    start_date: Optional[datetime] = Field(
        description="Start date for sync (defaults to 1 year ago)",
        example="2024-01-01"
    )
    
    end_date: Optional[datetime] = Field(
        description="End date for sync (defaults to today)",
        example="2024-12-31"
    )
    
    force_refresh: bool = Field(
        description="Force refresh even if data exists",
        default=False
    )


class MarketDataSyncResponse(BaseModel):
    """Response model for market data sync operation."""
    
    sync_id: str = Field(
        description="Unique sync operation ID",
        example="sync_20240101_123456"
    )
    
    symbols_synced: List[str] = Field(
        description="Symbols that were synced"
    )
    
    records_added: Dict[str, int] = Field(
        description="Records added per symbol",
        example={"SPY": 252, "QQQ": 252, "VIX": 252}
    )
    
    records_updated: Dict[str, int] = Field(
        description="Records updated per symbol",
        example={"SPY": 5, "QQQ": 3, "VIX": 2}
    )
    
    data_quality_scores: Dict[str, float] = Field(
        description="Data quality scores per symbol",
        example={"SPY": 0.98, "QQQ": 0.97, "VIX": 0.95}
    )
    
    sync_duration_seconds: float = Field(
        description="Time taken for sync operation",
        example=45.2
    )
    
    warnings: List[str] = Field(
        description="Any warnings during sync",
        example=["Some VIX data points had unusually high values"]
    )
    
    sync_timestamp: datetime = Field(
        description="When sync was completed",
        default_factory=datetime.now
    )


# Monte Carlo Simulation Models

class SimulationTypeEnum(str, Enum):
    """Types of Monte Carlo simulation."""
    BOOTSTRAP = "bootstrap"
    PARAMETRIC = "parametric"
    REGIME_CONDITIONAL = "regime_conditional"
    COMPREHENSIVE = "comprehensive"


class SimulationStatusEnum(str, Enum):
    """Status of Monte Carlo simulation."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class MonteCarloSimulationRequest(BaseModel):
    """Request model for Monte Carlo simulation."""
    
    simulation_type: SimulationTypeEnum = Field(
        description="Type of simulation to run",
        example="comprehensive"
    )
    
    num_scenarios: int = Field(
        description="Number of scenarios to generate",
        example=10000,
        ge=100,
        le=100000
    )
    
    scenario_length: int = Field(
        description="Length of each scenario (trading days)",
        example=252,
        ge=1,
        le=2520
    )
    
    confidence_levels: List[float] = Field(
        description="Confidence levels for risk metrics",
        example=[0.95, 0.99, 0.999],
        default=[0.95, 0.99, 0.999]
    )
    
    portfolio_value: float = Field(
        description="Portfolio value for percentage calculations",
        example=100000,
        gt=0
    )
    
    start_date: Optional[str] = Field(
        description="Start date for historical data (YYYY-MM-DD)",
        example="2023-01-01"
    )
    
    end_date: Optional[str] = Field(
        description="End date for historical data (YYYY-MM-DD)",
        example="2024-12-31"
    )
    
    random_seed: Optional[int] = Field(
        description="Random seed for reproducible results",
        example=42
    )
    
    parallel_processing: bool = Field(
        description="Enable parallel processing",
        default=True
    )
    
    max_workers: Optional[int] = Field(
        description="Maximum number of workers for parallel processing",
        example=4
    )
    
    enable_progress_tracking: bool = Field(
        description="Enable detailed progress tracking",
        default=True
    )


class VaRResultResponse(BaseModel):
    """Response model for Value at Risk result."""
    
    confidence_level: float = Field(
        description="Confidence level",
        example=0.95
    )
    
    var_absolute: float = Field(
        description="VaR in absolute terms",
        example=-2500.0
    )
    
    var_percentage: float = Field(
        description="VaR as percentage of portfolio",
        example=-2.5
    )
    
    calculation_method: str = Field(
        description="Calculation method used",
        example="monte_carlo"
    )
    
    sample_size: int = Field(
        description="Number of scenarios used",
        example=10000
    )
    
    percentile_rank: float = Field(
        description="Percentile rank in distribution",
        example=5.0
    )
    
    worst_case_scenario: Optional[float] = Field(
        description="Worst case scenario value",
        example=-8500.0
    )


class ExpectedShortfallResultResponse(BaseModel):
    """Response model for Expected Shortfall result."""
    
    confidence_level: float = Field(
        description="Confidence level",
        example=0.95
    )
    
    expected_shortfall: float = Field(
        description="Expected shortfall (average loss beyond VaR)",
        example=-3200.0
    )
    
    var_threshold: float = Field(
        description="VaR threshold",
        example=-2500.0
    )
    
    tail_scenarios_count: int = Field(
        description="Number of tail scenarios",
        example=500
    )
    
    calculation_method: str = Field(
        description="Calculation method",
        example="monte_carlo"
    )
    
    sample_size: int = Field(
        description="Total scenarios analyzed",
        example=10000
    )


class TailRiskMetricsResponse(BaseModel):
    """Response model for tail risk metrics."""
    model_config = {'protected_namespaces': ()}
    
    extreme_value_model: str = Field(
        description="Extreme value model used",
        example="generalized_extreme_value"
    )
    
    model_parameters: Dict[str, float] = Field(
        description="Model parameters",
        example={"shape": -0.1, "location": 2500, "scale": 800}
    )
    
    return_level_99_9: float = Field(
        description="99.9% return level (1 in 1000 event)",
        example=-5200.0
    )
    
    return_level_99_95: float = Field(
        description="99.95% return level (1 in 2000 event)",
        example=-6800.0
    )
    
    return_level_99_99: float = Field(
        description="99.99% return level (1 in 10000 event)",
        example=-9500.0
    )
    
    tail_index: Optional[float] = Field(
        description="Tail index for power law distributions",
        example=2.5
    )
    
    model_fit_quality: Dict[str, float] = Field(
        description="Goodness of fit metrics",
        example={"ks_statistic": 0.08, "ks_p_value": 0.42}
    )
    
    worst_historical_loss: float = Field(
        description="Worst historical loss observed",
        example=-4200.0
    )
    
    tail_concentration: float = Field(
        description="Concentration of losses in tail (0-1)",
        example=0.35
    )


class ProbabilityMetricsResponse(BaseModel):
    """Response model for probability-based metrics."""
    
    probability_of_profit: float = Field(
        description="Probability of positive return",
        example=0.62
    )
    
    probability_of_loss: float = Field(
        description="Probability of negative return", 
        example=0.38
    )
    
    probability_large_loss: Dict[str, float] = Field(
        description="Probability of large losses at thresholds",
        example={
            "loss_gt_1000": 0.15,
            "loss_gt_2000": 0.08,
            "loss_gt_5000": 0.02
        }
    )
    
    probability_large_gain: Dict[str, float] = Field(
        description="Probability of large gains at thresholds",
        example={
            "gain_gt_1000": 0.18,
            "gain_gt_2000": 0.12,
            "gain_gt_5000": 0.04
        }
    )
    
    expected_positive_return: float = Field(
        description="Expected return given positive outcome",
        example=850.0
    )
    
    expected_negative_return: float = Field(
        description="Expected return given negative outcome",
        example=-620.0
    )
    
    gain_loss_ratio: float = Field(
        description="Expected gain to expected loss ratio",
        example=1.37
    )
    
    kelly_criterion: Optional[float] = Field(
        description="Kelly criterion for optimal position sizing",
        example=0.08
    )


class SimulationProgressResponse(BaseModel):
    """Response model for simulation progress."""
    
    simulation_id: str = Field(
        description="Unique simulation identifier",
        example="sim_20240101_123456"
    )
    
    status: SimulationStatusEnum = Field(
        description="Current simulation status",
        example="running"
    )
    
    current_step: str = Field(
        description="Current processing step",
        example="Generating parametric scenarios"
    )
    
    steps_completed: int = Field(
        description="Number of steps completed",
        example=2
    )
    
    total_steps: int = Field(
        description="Total number of steps",
        example=5
    )
    
    progress_percentage: float = Field(
        description="Progress as percentage",
        example=40.0
    )
    
    start_time: datetime = Field(
        description="Simulation start time"
    )
    
    estimated_completion: Optional[datetime] = Field(
        description="Estimated completion time"
    )
    
    elapsed_time: float = Field(
        description="Elapsed time in seconds",
        example=125.5
    )
    
    scenarios_generated: int = Field(
        description="Number of scenarios generated so far",
        example=4000
    )
    
    total_scenarios_target: int = Field(
        description="Target number of scenarios",
        example=10000
    )
    
    current_operation: str = Field(
        description="Current operation description",
        example="Fitting probability distributions"
    )
    
    worker_count: int = Field(
        description="Number of parallel workers",
        example=4
    )
    
    memory_usage_mb: float = Field(
        description="Current memory usage in MB",
        example=256.5
    )
    
    error_message: Optional[str] = Field(
        description="Error message if failed"
    )


class ScenarioSummaryResponse(BaseModel):
    """Response model for scenario summary statistics."""
    
    total_scenarios: int = Field(
        description="Total number of scenarios",
        example=10000
    )
    
    mean_return: float = Field(
        description="Mean return across scenarios",
        example=125.5
    )
    
    std_return: float = Field(
        description="Standard deviation of returns",
        example=485.2
    )
    
    skewness: float = Field(
        description="Skewness of return distribution",
        example=-0.15
    )
    
    kurtosis: float = Field(
        description="Kurtosis of return distribution",
        example=2.8
    )
    
    min_scenario: float = Field(
        description="Worst scenario outcome",
        example=-4200.0
    )
    
    max_scenario: float = Field(
        description="Best scenario outcome",
        example=3800.0
    )
    
    median_scenario: float = Field(
        description="Median scenario outcome",
        example=98.5
    )


class RiskDecompositionResponse(BaseModel):
    """Response model for risk decomposition analysis."""
    
    worst_1_percent: float = Field(
        description="Average of worst 1% scenarios",
        example=-3200.0
    )
    
    worst_5_percent: float = Field(
        description="Average of worst 5% scenarios",
        example=-2100.0
    )
    
    worst_10_percent: float = Field(
        description="Average of worst 10% scenarios", 
        example=-1650.0
    )
    
    best_10_percent: float = Field(
        description="Average of best 10% scenarios",
        example=1950.0
    )
    
    middle_80_percent: float = Field(
        description="Average of middle 80% scenarios",
        example=145.0
    )
    
    interquartile_range: float = Field(
        description="Difference between 75th and 25th percentiles",
        example=680.0
    )
    
    range_ratio: float = Field(
        description="Range to standard deviation ratio",
        example=12.5
    )


class ComprehensiveRiskReportResponse(BaseModel):
    """Response model for comprehensive risk analysis report."""
    
    var_results: Dict[str, VaRResultResponse] = Field(
        description="VaR results at different confidence levels"
    )
    
    expected_shortfall_results: Dict[str, ExpectedShortfallResultResponse] = Field(
        description="Expected Shortfall results"
    )
    
    tail_risk_metrics: TailRiskMetricsResponse = Field(
        description="Tail risk analysis results"
    )
    
    probability_metrics: ProbabilityMetricsResponse = Field(
        description="Probability-based risk metrics"
    )
    
    scenario_summary: ScenarioSummaryResponse = Field(
        description="Summary statistics of scenarios"
    )
    
    risk_decomposition: RiskDecompositionResponse = Field(
        description="Risk contribution analysis"
    )
    
    regime_risk_analysis: Optional[Dict[str, Any]] = Field(
        description="Regime-specific risk analysis if applicable"
    )
    
    calculation_config: Dict[str, Any] = Field(
        description="Configuration used for calculations",
        example={
            "confidence_levels": [0.95, 0.99, 0.999],
            "portfolio_value": 100000,
            "generation_method": "parametric"
        }
    )
    
    generation_timestamp: datetime = Field(
        description="When report was generated"
    )


class MonteCarloSimulationResponse(BaseModel):
    """Response model for Monte Carlo simulation results."""
    
    simulation_id: str = Field(
        description="Unique simulation identifier",
        example="sim_20240101_123456"
    )
    
    simulation_type: SimulationTypeEnum = Field(
        description="Type of simulation performed"
    )
    
    status: SimulationStatusEnum = Field(
        description="Simulation status"
    )
    
    risk_report: Optional[ComprehensiveRiskReportResponse] = Field(
        description="Comprehensive risk analysis results"
    )
    
    progress: SimulationProgressResponse = Field(
        description="Simulation progress information"
    )
    
    performance_metrics: Dict[str, Any] = Field(
        description="Simulation performance metrics",
        example={
            "total_execution_time": 125.5,
            "parallel_efficiency": 0.85,
            "memory_peak_usage_mb": 512.3
        }
    )
    
    account_name: str = Field(
        description="Account analyzed"
    )
    
    time_bin: str = Field(
        description="Time bin analyzed",
        example="09:30"
    )
    
    request_timestamp: datetime = Field(
        description="When simulation was requested"
    )
    
    completion_timestamp: Optional[datetime] = Field(
        description="When simulation completed"
    )


# Walk-Forward Analysis API Models

class ValidationMethodEnum(str, Enum):
    """Validation method types."""
    ANCHORED_WALK_FORWARD = "anchored_walk_forward"
    ROLLING_WINDOW = "rolling_window"
    EXPANDING_WINDOW = "expanding_window"
    TIME_SERIES_CV = "time_series_cv"


class DegradationSeverityEnum(str, Enum):
    """Strategy degradation severity levels."""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class AlertTypeEnum(str, Enum):
    """Performance alert types."""
    PERFORMANCE_DROP = "performance_drop"
    ACCURACY_DECLINE = "accuracy_decline"
    CONSISTENCY_LOSS = "consistency_loss"
    RETRAINING_NEEDED = "retraining_needed"
    STRATEGY_FAILURE = "strategy_failure"


class WalkForwardValidationRequest(BaseModel):
    """Request model for walk-forward validation."""
    
    validation_method: ValidationMethodEnum = Field(
        description="Validation method to use",
        example="anchored_walk_forward"
    )
    
    start_date: str = Field(
        description="Start date for analysis (YYYY-MM-DD)",
        example="2024-01-01"
    )
    
    end_date: str = Field(
        description="End date for analysis (YYYY-MM-DD)",
        example="2024-06-30"
    )
    
    min_in_sample_days: int = Field(
        default=30,
        description="Minimum in-sample period in days",
        example=30,
        ge=7,
        le=365
    )
    
    out_of_sample_days: int = Field(
        default=10,
        description="Out-of-sample period in days",
        example=10,
        ge=1,
        le=90
    )
    
    step_days: int = Field(
        default=5,
        description="Step size in days for validation windows",
        example=5,
        ge=1,
        le=30
    )
    
    min_trades_threshold: int = Field(
        default=10,
        description="Minimum trades required for valid period",
        example=10,
        ge=5,
        le=100
    )
    
    performance_stability_threshold: float = Field(
        default=0.3,
        description="Performance stability threshold",
        example=0.3,
        ge=0.1,
        le=1.0
    )
    
    overfitting_detection_threshold: float = Field(
        default=0.5,
        description="Overfitting detection threshold",
        example=0.5,
        ge=0.1,
        le=2.0
    )
    
    confidence_level: float = Field(
        default=0.95,
        description="Statistical confidence level",
        example=0.95,
        ge=0.8,
        le=0.999
    )
    
    # Cross-validation specific parameters
    n_splits: Optional[int] = Field(
        default=None,
        description="Number of splits for cross-validation",
        example=5,
        ge=2,
        le=20
    )
    
    test_size_ratio: Optional[float] = Field(
        default=None,
        description="Test size ratio for cross-validation",
        example=0.2,
        gt=0.0,
        lt=0.5
    )
    
    gap_days: Optional[int] = Field(
        default=None,
        description="Gap days between train/test in cross-validation",
        example=2,
        ge=0,
        le=30
    )


class PerformanceMetricsResponse(BaseModel):
    """Response model for performance metrics."""
    
    total_trades: int = Field(
        description="Total number of trades",
        example=50
    )
    
    winning_trades: int = Field(
        description="Number of winning trades",
        example=32
    )
    
    losing_trades: int = Field(
        description="Number of losing trades",
        example=18
    )
    
    win_rate: float = Field(
        description="Win rate as decimal",
        example=0.64
    )
    
    average_pnl: float = Field(
        description="Average P&L per trade",
        example=125.50
    )
    
    total_pnl: float = Field(
        description="Total P&L",
        example=6275.0
    )
    
    profit_factor: Optional[float] = Field(
        description="Profit factor",
        example=2.58
    )
    
    sharpe_ratio: Optional[float] = Field(
        description="Sharpe ratio",
        example=1.45
    )
    
    max_drawdown_pct: Optional[float] = Field(
        description="Maximum drawdown percentage",
        example=8.5
    )
    
    calmar_ratio: Optional[float] = Field(
        description="Calmar ratio",
        example=0.171
    )


class PeriodPerformanceResponse(BaseModel):
    """Response model for individual period performance."""
    
    period_id: str = Field(
        description="Period identifier",
        example="period_2024_01_01_to_2024_01_31"
    )
    
    in_sample_start: datetime = Field(
        description="In-sample period start"
    )
    
    in_sample_end: datetime = Field(
        description="In-sample period end"
    )
    
    out_of_sample_start: datetime = Field(
        description="Out-of-sample period start"
    )
    
    out_of_sample_end: datetime = Field(
        description="Out-of-sample period end"
    )
    
    in_sample_metrics: PerformanceMetricsResponse = Field(
        description="In-sample performance metrics"
    )
    
    out_of_sample_metrics: PerformanceMetricsResponse = Field(
        description="Out-of-sample performance metrics"
    )
    
    trades_count_in_sample: int = Field(
        description="Number of trades in in-sample period",
        example=45
    )
    
    trades_count_out_of_sample: int = Field(
        description="Number of trades in out-of-sample period",
        example=15
    )


class WalkForwardValidationResponse(BaseModel):
    """Response model for walk-forward validation results."""
    
    validation_id: str = Field(
        description="Unique validation identifier",
        example="wf_20240101_123456"
    )
    
    validation_method: ValidationMethodEnum = Field(
        description="Validation method used"
    )
    
    account_name: str = Field(
        description="Account analyzed"
    )
    
    time_bin: str = Field(
        description="Time bin analyzed",
        example="09:30"
    )
    
    analysis_period: Dict[str, Any] = Field(
        description="Analysis period information",
        example={
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "total_periods": 12
        }
    )
    
    period_performances: List[PeriodPerformanceResponse] = Field(
        description="Performance results for each validation period"
    )
    
    overall_metrics: Dict[str, float] = Field(
        description="Overall validation metrics",
        example={
            "avg_out_of_sample_sharpe": 1.25,
            "avg_out_of_sample_win_rate": 0.62,
            "overall_robustness_score": 0.78
        }
    )
    
    stability_analysis: Dict[str, Any] = Field(
        description="Performance stability analysis",
        example={
            "sharpe_ratio_std": 0.25,
            "sharpe_ratio_cv": 0.20,
            "performance_consistency": 0.85
        }
    )
    
    overfitting_analysis: Dict[str, float] = Field(
        description="Overfitting detection results",
        example={
            "avg_sharpe_gap": 0.15,
            "overfitting_risk_score": 0.25,
            "periods_with_large_gaps": 2
        }
    )
    
    consistency_analysis: Dict[str, float] = Field(
        description="Performance consistency analysis",
        example={
            "positive_period_ratio": 0.75,
            "good_sharpe_period_ratio": 0.67,
            "overall_consistency_score": 0.71
        }
    )
    
    recommendation: str = Field(
        description="Strategy recommendation based on validation",
        example="RECOMMENDED - Strategy demonstrates good robustness with acceptable stability"
    )
    
    generation_timestamp: datetime = Field(
        description="When validation was performed",
        default_factory=datetime.now
    )


class DegradationAlertResponse(BaseModel):
    """Response model for degradation alerts."""
    
    alert_type: AlertTypeEnum = Field(
        description="Type of alert"
    )
    
    severity: DegradationSeverityEnum = Field(
        description="Alert severity level"
    )
    
    message: str = Field(
        description="Human-readable alert message",
        example="Sharpe Ratio has decreased significantly. Current: 0.85, Historical: 1.25"
    )
    
    metric_name: str = Field(
        description="Performance metric that triggered alert",
        example="sharpe_ratio"
    )
    
    current_value: float = Field(
        description="Current metric value",
        example=0.85
    )
    
    threshold_value: float = Field(
        description="Threshold or historical value",
        example=1.25
    )
    
    confidence_level: float = Field(
        description="Confidence in alert",
        example=0.92
    )
    
    detected_at: datetime = Field(
        description="When alert was detected"
    )
    
    recommended_action: str = Field(
        description="Recommended action",
        example="WARNING: Monitor closely and consider retraining model within 1-2 days"
    )


class StrategyRobustnessResponse(BaseModel):
    """Response model for strategy robustness analysis."""
    
    robustness_id: str = Field(
        description="Unique robustness analysis identifier",
        example="rob_20240101_123456"
    )
    
    account_name: str = Field(
        description="Account analyzed"
    )
    
    time_bin: str = Field(
        description="Time bin analyzed",
        example="09:30"
    )
    
    overall_robustness_score: float = Field(
        description="Overall robustness score (0-1)",
        example=0.78
    )
    
    degradation_severity: DegradationSeverityEnum = Field(
        description="Current degradation severity"
    )
    
    active_alerts: List[DegradationAlertResponse] = Field(
        description="Active degradation alerts"
    )
    
    performance_trends: Dict[str, float] = Field(
        description="Recent performance trends",
        example={
            "sharpe_ratio_trend": -0.02,
            "win_rate_trend": -0.01,
            "average_pnl_trend": -5.5
        }
    )
    
    time_to_failure_estimate: Optional[float] = Field(
        description="Estimated days until strategy failure",
        example=45.0
    )
    
    confidence_in_assessment: float = Field(
        description="Confidence in robustness assessment",
        example=0.88
    )
    
    key_degraded_metrics: List[str] = Field(
        description="Metrics showing significant degradation",
        example=["sharpe_ratio", "win_rate"]
    )
    
    recommendation: str = Field(
        description="Strategy recommendation",
        example="MODERATE DEGRADATION DETECTED: Reduce position sizes by 25-50%"
    )
    
    next_monitoring_interval_hours: float = Field(
        description="Recommended next monitoring interval in hours",
        example=24.0
    )
    
    analysis_timestamp: datetime = Field(
        description="When analysis was performed",
        default_factory=datetime.now
    )


class PredictionAccuracyRequest(BaseModel):
    """Request model for prediction accuracy analysis."""
    
    prediction_period_days: int = Field(
        default=30,
        description="Number of days to analyze for prediction accuracy",
        example=30,
        ge=7,
        le=180
    )
    
    start_date: Optional[str] = Field(
        default=None,
        description="Start date for analysis (YYYY-MM-DD)",
        example="2024-01-01"
    )
    
    end_date: Optional[str] = Field(
        default=None,
        description="End date for analysis (YYYY-MM-DD)",
        example="2024-06-30"
    )
    
    include_confidence_intervals: bool = Field(
        default=True,
        description="Include bootstrap confidence intervals",
        example=True
    )
    
    significance_level: float = Field(
        default=0.05,
        description="Statistical significance level",
        example=0.05,
        gt=0.0,
        lt=0.5
    )


class RetrainingAnalysisRequest(BaseModel):
    """Request model for retraining frequency analysis."""
    
    lookback_days: int = Field(
        default=90,
        description="Days to look back for retraining analysis",
        example=90,
        ge=30,
        le=365
    )
    
    retraining_cost_factor: float = Field(
        default=1.0,
        description="Relative cost factor for retraining",
        example=1.0,
        ge=0.1,
        le=10.0
    )
    
    performance_weight_recent: float = Field(
        default=0.7,
        description="Weight given to recent performance",
        example=0.7,
        ge=0.1,
        le=1.0
    )


class DecayAnalysisResponse(BaseModel):
    """Response model for comprehensive decay analysis."""
    
    analysis_id: str = Field(
        description="Unique analysis identifier",
        example="decay_20240101_123456"
    )
    
    account_name: str = Field(
        description="Account analyzed"
    )
    
    time_bin: str = Field(
        description="Time bin analyzed",
        example="09:30"
    )
    
    # Prediction accuracy results
    prediction_accuracy: Dict[str, Any] = Field(
        description="Prediction accuracy metrics",
        example={
            "correlation_coefficient": 0.75,
            "directional_accuracy": 0.68,
            "mean_squared_error": 125.5,
            "r_squared": 0.56,
            "accuracy_trend": -0.02
        }
    )
    
    # Retraining analysis results
    retraining_analysis: Dict[str, Any] = Field(
        description="Optimal retraining frequency analysis",
        example={
            "current_model_age_days": 45,
            "optimal_retraining_days": 21,
            "performance_decay_rate": 0.008,
            "retraining_benefit_score": 0.15,
            "next_recommended_retraining": "2024-07-15"
        }
    )
    
    # Strategy degradation results
    degradation_assessment: StrategyRobustnessResponse = Field(
        description="Current strategy degradation assessment"
    )
    
    # Performance persistence results
    persistence_analysis: Dict[str, Any] = Field(
        description="Performance persistence analysis",
        example={
            "persistence_score": 0.45,
            "mean_reversion_tendency": 0.35,
            "autocorrelation_lag_1": 0.25,
            "predictability_score": 0.60
        }
    )
    
    # Overall assessment
    overall_health_score: float = Field(
        description="Overall strategy health score (0-1)",
        example=0.72
    )
    
    priority_actions: List[str] = Field(
        description="Prioritized list of recommended actions",
        example=[
            "Monitor Sharpe ratio degradation closely",
            "Schedule model retraining in 2 weeks",
            "Consider reducing position sizes by 25%"
        ]
    )
    
    analysis_timestamp: datetime = Field(
        description="When analysis was performed",
        default_factory=datetime.now
    )


class BackgroundProcessRequest(BaseModel):
    """Request model for background processing."""
    
    process_type: str = Field(
        description="Type of background process",
        example="walk_forward_validation"
    )
    
    priority: int = Field(
        default=1,
        description="Process priority (1=high, 5=low)",
        example=1,
        ge=1,
        le=5
    )
    
    max_execution_time_minutes: int = Field(
        default=60,
        description="Maximum execution time in minutes",
        example=60,
        ge=1,
        le=480
    )
    
    enable_progress_tracking: bool = Field(
        default=True,
        description="Enable progress tracking and updates",
        example=True
    )


class BackgroundProcessResponse(BaseModel):
    """Response model for background process status."""
    
    process_id: str = Field(
        description="Unique process identifier",
        example="proc_20240101_123456"
    )
    
    process_type: str = Field(
        description="Type of background process",
        example="walk_forward_validation"
    )
    
    status: str = Field(
        description="Current process status",
        example="running"
    )
    
    progress_percentage: float = Field(
        description="Progress as percentage",
        example=65.0
    )
    
    current_operation: str = Field(
        description="Current operation description",
        example="Processing validation period 8 of 12"
    )
    
    start_time: datetime = Field(
        description="Process start time"
    )
    
    estimated_completion: Optional[datetime] = Field(
        description="Estimated completion time"
    )
    
    elapsed_time_seconds: float = Field(
        description="Elapsed time in seconds",
        example=1250.5
    )
    
    result_url: Optional[str] = Field(
        description="URL to retrieve results when complete",
        example="/api/time-bins/IPS_TM_10/9/30/walk-forward/results/proc_20240101_123456"
    )
    
    error_message: Optional[str] = Field(
        description="Error message if failed"
    )