"""
FastAPI endpoints for backtesting and analysis.

This module provides REST API endpoints for running backtests, analyzing results,
and managing backtesting configurations and strategies.

Requirements: 9.1, 9.2, 9.3, 10.2
"""

import logging
import asyncio
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any, Union
from fastapi import APIRouter, HTTPException, Depends, Query, Path, Body, BackgroundTasks
from pydantic import BaseModel, Field, validator
from enum import Enum
import json
import uuid

from ...services.backtesting.time_bin_backtesting_engine import (
    TimeBinBacktestingEngine, BacktestConfiguration, BacktestMethod,
    PerformanceMetric, TradeSignal, BacktestResult, BacktestPeriodResult
)
from ...services.backtesting.backtest_results_analyzer import (
    BacktestResultsAnalyzer, AnalysisType, ComprehensiveAnalysis
)
from ...services.time_bin_analyzer import TimeBin, TimeBinAnalyzer
from ...services.monte_carlo.monte_carlo_simulator import MonteCarloSimulator
from ...services.statistical_testing_engine import StatisticalTestingEngine

logger = logging.getLogger(__name__)

# Router for backtesting endpoints
router = APIRouter(prefix="/api/backtesting", tags=["backtesting"])

# Global instances - would be dependency injected in production
backtesting_engine: Optional[TimeBinBacktestingEngine] = None
results_analyzer: Optional[BacktestResultsAnalyzer] = None
time_bin_analyzer: Optional[TimeBinAnalyzer] = None

# Background task storage
active_backtests: Dict[str, Dict[str, Any]] = {}
completed_backtests: Dict[str, BacktestResult] = {}
analysis_cache: Dict[str, ComprehensiveAnalysis] = {}


# Pydantic models for API requests/responses
class BacktestMethodEnum(str, Enum):
    """Backtesting method enumeration."""
    SIMPLE_HISTORICAL = "simple_historical"
    WALK_FORWARD = "walk_forward"
    MONTE_CARLO = "monte_carlo"
    BOOTSTRAP = "bootstrap"
    CROSS_VALIDATION = "cross_validation"


class PerformanceMetricEnum(str, Enum):
    """Performance metric enumeration."""
    TOTAL_RETURN = "total_return"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SORTINO_RATIO = "sortino_ratio"
    CALMAR_RATIO = "calmar_ratio"


class AnalysisTypeEnum(str, Enum):
    """Analysis type enumeration."""
    PERFORMANCE_ATTRIBUTION = "performance_attribution"
    RISK_DECOMPOSITION = "risk_decomposition"
    TRADE_ANALYSIS = "trade_analysis"
    TEMPORAL_ANALYSIS = "temporal_analysis"
    STATISTICAL_VALIDATION = "statistical_validation"
    COMPARATIVE_ANALYSIS = "comparative_analysis"
    SENSITIVITY_ANALYSIS = "sensitivity_analysis"


class TimeBinRequest(BaseModel):
    """Time-bin specification for backtesting."""
    account_name: str = Field(..., description="Trading account name")
    hour: int = Field(..., ge=0, le=23, description="Hour of the day (0-23)")
    minute_bin: int = Field(..., ge=0, le=59, description="Minute bin (0-59)")


class BacktestConfigRequest(BaseModel):
    """Backtesting configuration request."""
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    initial_capital: float = Field(default=100000.0, gt=0, description="Initial capital")
    commission_per_trade: float = Field(default=1.0, ge=0, description="Commission per trade")
    slippage_bps: int = Field(default=1, ge=0, le=100, description="Slippage in basis points")
    method: BacktestMethodEnum = Field(default=BacktestMethodEnum.SIMPLE_HISTORICAL, description="Backtesting method")
    
    # Walk-forward specific
    training_days: int = Field(default=252, gt=0, description="Training period in days")
    testing_days: int = Field(default=63, gt=0, description="Testing period in days")
    rebalance_frequency: int = Field(default=21, gt=0, description="Rebalance frequency in days")
    
    # Monte Carlo specific
    num_simulations: int = Field(default=1000, ge=10, le=10000, description="Number of Monte Carlo simulations")
    confidence_levels: List[float] = Field(default=[0.95, 0.99], description="Confidence levels for analysis")
    
    # Cross-validation specific
    num_folds: int = Field(default=5, ge=2, le=10, description="Number of cross-validation folds")
    
    # Performance evaluation
    benchmark_symbol: str = Field(default="SPY", description="Benchmark symbol")
    risk_free_rate: float = Field(default=0.02, ge=0, le=1, description="Risk-free rate")
    target_metrics: List[PerformanceMetricEnum] = Field(
        default=[
            PerformanceMetricEnum.TOTAL_RETURN,
            PerformanceMetricEnum.SHARPE_RATIO,
            PerformanceMetricEnum.MAX_DRAWDOWN,
            PerformanceMetricEnum.WIN_RATE
        ],
        description="Target performance metrics"
    )
    
    @validator('end_date')
    def end_date_after_start_date(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class StrategyParametersRequest(BaseModel):
    """Strategy parameters for backtesting."""
    strategy_name: str = Field(..., description="Name of the strategy")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Strategy-specific parameters")
    signal_threshold: float = Field(default=0.5, ge=0, le=1, description="Signal confidence threshold")
    position_sizing: str = Field(default="equal_weight", description="Position sizing method")
    max_positions: int = Field(default=10, ge=1, description="Maximum number of concurrent positions")


class BacktestRequest(BaseModel):
    """Complete backtesting request."""
    configuration: BacktestConfigRequest
    time_bins: List[TimeBinRequest]
    strategy_parameters: StrategyParametersRequest
    run_analysis: bool = Field(default=True, description="Whether to run comprehensive analysis")
    analysis_types: List[AnalysisTypeEnum] = Field(
        default_factory=lambda: [
            AnalysisTypeEnum.PERFORMANCE_ATTRIBUTION,
            AnalysisTypeEnum.RISK_DECOMPOSITION,
            AnalysisTypeEnum.TRADE_ANALYSIS,
            AnalysisTypeEnum.STATISTICAL_VALIDATION
        ],
        description="Types of analysis to perform"
    )


class BacktestStatus(BaseModel):
    """Backtesting status response."""
    backtest_id: str
    status: str  # PENDING, RUNNING, COMPLETED, FAILED
    progress: float = Field(ge=0, le=1, description="Progress percentage (0-1)")
    started_at: datetime
    estimated_completion: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class TradeResponse(BaseModel):
    """Trade result response."""
    entry_time: datetime
    exit_time: Optional[datetime]
    time_bin: TimeBinRequest
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    trade_type: str
    pnl: Optional[float]
    commission: float
    slippage: float
    is_closed: bool


class PeriodResultResponse(BaseModel):
    """Period result response."""
    start_date: date
    end_date: date
    initial_capital: float
    final_capital: float
    total_return: float
    num_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_pnl: float
    max_drawdown: float
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    profit_factor: Optional[float]
    win_rate: float
    total_commission: float
    total_slippage: float
    
    # Optional detailed data
    trades: Optional[List[TradeResponse]] = None
    daily_returns: Optional[List[float]] = None


class BacktestResultResponse(BaseModel):
    """Backtesting result response."""
    backtest_id: str
    configuration: BacktestConfigRequest
    method: BacktestMethodEnum
    overall_result: PeriodResultResponse
    period_results: List[PeriodResultResponse] = Field(default_factory=list)
    
    # Method-specific results
    simulation_results: Optional[List[PeriodResultResponse]] = None
    percentile_results: Optional[Dict[str, Any]] = None
    out_of_sample_results: Optional[List[PeriodResultResponse]] = None
    in_sample_results: Optional[List[PeriodResultResponse]] = None
    fold_results: Optional[List[PeriodResultResponse]] = None
    
    # Performance benchmarking
    benchmark_comparison: Optional[Dict[str, Any]] = None
    
    # Execution metadata
    execution_time_seconds: float
    timestamp: datetime


class AnalysisRequest(BaseModel):
    """Analysis request for backtesting results."""
    backtest_id: str = Field(..., description="Backtest ID to analyze")
    analysis_types: List[AnalysisTypeEnum] = Field(
        default_factory=lambda: list(AnalysisTypeEnum),
        description="Types of analysis to perform"
    )
    benchmark_backtest_ids: List[str] = Field(
        default_factory=list,
        description="Benchmark backtest IDs for comparison"
    )
    cache_results: bool = Field(default=True, description="Whether to cache analysis results")


class AnalysisResultResponse(BaseModel):
    """Analysis result response."""
    analysis_id: str
    backtest_id: str
    analysis_timestamp: datetime
    overall_quality_score: float
    recommendation: str
    key_insights: List[str]
    
    # Analysis components (simplified for API response)
    performance_attribution: Optional[Dict[str, Any]] = None
    risk_decomposition: Optional[Dict[str, Any]] = None
    trade_analysis: Optional[Dict[str, Any]] = None
    temporal_analysis: Optional[Dict[str, Any]] = None
    statistical_validation: Optional[Dict[str, Any]] = None
    comparative_analysis: Optional[Dict[str, Any]] = None
    sensitivity_analysis: Optional[Dict[str, Any]] = None


# Dependency functions
def get_backtesting_engine() -> TimeBinBacktestingEngine:
    """Get backtesting engine dependency."""
    if backtesting_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Backtesting engine not initialized"
        )
    return backtesting_engine


def get_results_analyzer() -> BacktestResultsAnalyzer:
    """Get results analyzer dependency."""
    if results_analyzer is None:
        raise HTTPException(
            status_code=503,
            detail="Results analyzer not initialized"
        )
    return results_analyzer


def get_time_bin_analyzer() -> TimeBinAnalyzer:
    """Get time-bin analyzer dependency."""
    if time_bin_analyzer is None:
        raise HTTPException(
            status_code=503,
            detail="Time-bin analyzer not initialized"
        )
    return time_bin_analyzer


# Strategy function placeholder - would be replaced with actual strategy logic
async def example_strategy_function(time_bin: TimeBin, current_datetime: datetime, context: Dict[str, Any]) -> Optional[TradeSignal]:
    """
    Example strategy function for demonstration.
    
    In production, this would be replaced with actual strategy implementations
    or loaded dynamically based on strategy parameters.
    """
    # Simple example: buy signal if it's the first trading hour of the day
    if current_datetime.hour == 9 and current_datetime.minute < 30:
        return TradeSignal(
            timestamp=current_datetime,
            time_bin=time_bin,
            signal_type='BUY',
            confidence=0.7,
            price=100.0,  # Placeholder price
            metadata={'strategy': 'example', 'reason': 'market_open'}
        )
    
    # Sell signal later in the day
    elif current_datetime.hour == 15 and current_datetime.minute > 30:
        return TradeSignal(
            timestamp=current_datetime,
            time_bin=time_bin,
            signal_type='SELL',
            confidence=0.6,
            price=101.0,  # Placeholder price
            metadata={'strategy': 'example', 'reason': 'market_close'}
        )
    
    return None


# API Endpoints
@router.post("/run", response_model=BacktestStatus)
async def run_backtest(
    backtest_request: BacktestRequest,
    background_tasks: BackgroundTasks,
    engine: TimeBinBacktestingEngine = Depends(get_backtesting_engine)
) -> BacktestStatus:
    """
    Start a new backtesting job.
    
    Initiates backtesting with the specified configuration and strategy parameters.
    Returns immediately with a backtest ID for status tracking.
    """
    backtest_id = str(uuid.uuid4())
    
    try:
        # Convert request models to internal types
        config = BacktestConfiguration(
            start_date=backtest_request.configuration.start_date,
            end_date=backtest_request.configuration.end_date,
            initial_capital=backtest_request.configuration.initial_capital,
            commission_per_trade=backtest_request.configuration.commission_per_trade,
            slippage_bps=backtest_request.configuration.slippage_bps,
            method=BacktestMethod(backtest_request.configuration.method.value),
            training_days=backtest_request.configuration.training_days,
            testing_days=backtest_request.configuration.testing_days,
            rebalance_frequency=backtest_request.configuration.rebalance_frequency,
            num_simulations=backtest_request.configuration.num_simulations,
            confidence_levels=backtest_request.configuration.confidence_levels,
            num_folds=backtest_request.configuration.num_folds,
            benchmark_symbol=backtest_request.configuration.benchmark_symbol,
            risk_free_rate=backtest_request.configuration.risk_free_rate
        )
        
        time_bins = [
            TimeBin(tb.account_name, tb.hour, tb.minute_bin)
            for tb in backtest_request.time_bins
        ]
        
        # Store backtest info
        active_backtests[backtest_id] = {
            'status': 'PENDING',
            'progress': 0.0,
            'started_at': datetime.now(),
            'config': config,
            'time_bins': time_bins,
            'strategy_params': backtest_request.strategy_parameters.dict(),
            'run_analysis': backtest_request.run_analysis,
            'analysis_types': [AnalysisType(at.value) for at in backtest_request.analysis_types]
        }
        
        # Start background task
        background_tasks.add_task(
            _run_backtest_background,
            backtest_id,
            config,
            time_bins,
            backtest_request.strategy_parameters.dict(),
            backtest_request.run_analysis,
            [AnalysisType(at.value) for at in backtest_request.analysis_types]
        )
        
        logger.info(f"Started backtest {backtest_id}")
        
        return BacktestStatus(
            backtest_id=backtest_id,
            status='PENDING',
            progress=0.0,
            started_at=active_backtests[backtest_id]['started_at']
        )
        
    except Exception as e:
        logger.error(f"Failed to start backtest: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start backtest: {str(e)}"
        )


@router.get("/status/{backtest_id}", response_model=BacktestStatus)
async def get_backtest_status(
    backtest_id: str = Path(..., description="Backtest ID")
) -> BacktestStatus:
    """
    Get the status of a running or completed backtest.
    
    Returns current progress and status information for the specified backtest.
    """
    if backtest_id in active_backtests:
        backtest_info = active_backtests[backtest_id]
        return BacktestStatus(
            backtest_id=backtest_id,
            status=backtest_info['status'],
            progress=backtest_info['progress'],
            started_at=backtest_info['started_at'],
            estimated_completion=backtest_info.get('estimated_completion'),
            completed_at=backtest_info.get('completed_at'),
            error_message=backtest_info.get('error_message')
        )
    
    elif backtest_id in completed_backtests:
        # Backtest is completed
        return BacktestStatus(
            backtest_id=backtest_id,
            status='COMPLETED',
            progress=1.0,
            started_at=datetime.now(),  # Would store actual start time
            completed_at=datetime.now()  # Would store actual completion time
        )
    
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {backtest_id} not found"
        )


@router.get("/results/{backtest_id}", response_model=BacktestResultResponse)
async def get_backtest_results(
    backtest_id: str = Path(..., description="Backtest ID"),
    include_trades: bool = Query(default=False, description="Include detailed trade data"),
    include_daily_returns: bool = Query(default=False, description="Include daily returns data")
) -> BacktestResultResponse:
    """
    Get the results of a completed backtest.
    
    Returns comprehensive backtesting results including performance metrics,
    trades, and analysis data.
    """
    if backtest_id not in completed_backtests:
        if backtest_id in active_backtests:
            backtest_info = active_backtests[backtest_id]
            if backtest_info['status'] != 'COMPLETED':
                raise HTTPException(
                    status_code=409,
                    detail=f"Backtest {backtest_id} is still running. Status: {backtest_info['status']}"
                )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Backtest {backtest_id} not found"
            )
    
    try:
        result = completed_backtests[backtest_id]
        
        # Convert internal result to API response format
        response = _convert_backtest_result_to_response(
            backtest_id, result, include_trades, include_daily_returns
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get backtest results for {backtest_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve backtest results: {str(e)}"
        )


@router.post("/analyze", response_model=str)
async def run_analysis(
    analysis_request: AnalysisRequest,
    background_tasks: BackgroundTasks,
    analyzer: BacktestResultsAnalyzer = Depends(get_results_analyzer)
) -> str:
    """
    Run comprehensive analysis on backtesting results.
    
    Performs detailed analysis including performance attribution, risk decomposition,
    and statistical validation. Returns analysis ID for tracking.
    """
    if analysis_request.backtest_id not in completed_backtests:
        raise HTTPException(
            status_code=404,
            detail=f"Backtest {analysis_request.backtest_id} not found or not completed"
        )
    
    analysis_id = str(uuid.uuid4())
    
    try:
        # Get benchmark results if specified
        benchmark_results = []
        for benchmark_id in analysis_request.benchmark_backtest_ids:
            if benchmark_id in completed_backtests:
                benchmark_results.append(completed_backtests[benchmark_id])
            else:
                logger.warning(f"Benchmark backtest {benchmark_id} not found, skipping")
        
        # Start background analysis
        background_tasks.add_task(
            _run_analysis_background,
            analysis_id,
            analysis_request.backtest_id,
            [AnalysisType(at.value) for at in analysis_request.analysis_types],
            benchmark_results,
            analysis_request.cache_results
        )
        
        logger.info(f"Started analysis {analysis_id} for backtest {analysis_request.backtest_id}")
        
        return analysis_id
        
    except Exception as e:
        logger.error(f"Failed to start analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start analysis: {str(e)}"
        )


@router.get("/analysis/{analysis_id}", response_model=AnalysisResultResponse)
async def get_analysis_results(
    analysis_id: str = Path(..., description="Analysis ID")
) -> AnalysisResultResponse:
    """
    Get the results of a completed analysis.
    
    Returns comprehensive analysis results including performance attribution,
    risk metrics, and recommendations.
    """
    if analysis_id not in analysis_cache:
        raise HTTPException(
            status_code=404,
            detail=f"Analysis {analysis_id} not found or not completed"
        )
    
    try:
        analysis = analysis_cache[analysis_id]
        
        # Convert internal analysis to API response format
        response = _convert_analysis_to_response(analysis_id, analysis)
        
        return response
        
    except Exception as e:
        logger.error(f"Failed to get analysis results for {analysis_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve analysis results: {str(e)}"
        )


@router.get("/list", response_model=List[Dict[str, Any]])
async def list_backtests(
    status: Optional[str] = Query(None, description="Filter by status (PENDING, RUNNING, COMPLETED, FAILED)"),
    limit: int = Query(default=50, ge=1, le=1000, description="Maximum number of results")
) -> List[Dict[str, Any]]:
    """
    List all backtests with optional filtering.
    
    Returns a list of backtest summaries with basic information.
    """
    try:
        backtests = []
        
        # Add active backtests
        for backtest_id, info in active_backtests.items():
            if status is None or info['status'] == status:
                backtests.append({
                    'backtest_id': backtest_id,
                    'status': info['status'],
                    'started_at': info['started_at'],
                    'progress': info['progress'],
                    'method': info['config'].method.value,
                    'num_time_bins': len(info['time_bins'])
                })
        
        # Add completed backtests
        if status is None or status == 'COMPLETED':
            for backtest_id, result in completed_backtests.items():
                backtests.append({
                    'backtest_id': backtest_id,
                    'status': 'COMPLETED',
                    'started_at': result.timestamp,
                    'progress': 1.0,
                    'method': result.method.value,
                    'total_return': result.overall_result.total_return,
                    'sharpe_ratio': result.overall_result.sharpe_ratio,
                    'max_drawdown': result.overall_result.max_drawdown
                })
        
        # Sort by start time (newest first) and apply limit
        backtests.sort(key=lambda x: x.get('started_at', datetime.min), reverse=True)
        
        return backtests[:limit]
        
    except Exception as e:
        logger.error(f"Failed to list backtests: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list backtests: {str(e)}"
        )


@router.delete("/results/{backtest_id}")
async def delete_backtest(
    backtest_id: str = Path(..., description="Backtest ID to delete")
) -> Dict[str, str]:
    """
    Delete a backtest and its results.
    
    Removes backtest data from memory and cancels if still running.
    """
    try:
        deleted = False
        
        # Remove from active backtests
        if backtest_id in active_backtests:
            del active_backtests[backtest_id]
            deleted = True
        
        # Remove from completed backtests
        if backtest_id in completed_backtests:
            del completed_backtests[backtest_id]
            deleted = True
        
        # Remove associated analyses
        analyses_to_remove = [
            aid for aid, analysis in analysis_cache.items()
            if analysis.backtest_result.timestamp  # Would check backtest_id if stored
        ]
        
        for analysis_id in analyses_to_remove:
            del analysis_cache[analysis_id]
        
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=f"Backtest {backtest_id} not found"
            )
        
        logger.info(f"Deleted backtest {backtest_id}")
        
        return {"message": f"Backtest {backtest_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backtest {backtest_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete backtest: {str(e)}"
        )


@router.get("/strategies", response_model=List[Dict[str, Any]])
async def list_available_strategies() -> List[Dict[str, Any]]:
    """
    List available backtesting strategies.
    
    Returns information about available strategy implementations.
    """
    # This would typically load from a strategy registry
    # For now, return example strategies
    
    strategies = [
        {
            'strategy_name': 'example_strategy',
            'description': 'Example time-bin strategy for demonstration',
            'parameters': {
                'signal_threshold': {'type': 'float', 'default': 0.5, 'min': 0.0, 'max': 1.0},
                'position_sizing': {'type': 'string', 'default': 'equal_weight', 'options': ['equal_weight', 'volatility_adjusted']},
                'max_positions': {'type': 'integer', 'default': 10, 'min': 1, 'max': 50}
            },
            'supported_time_bins': 'all',
            'recommended_capital': 100000.0
        },
        {
            'strategy_name': 'momentum_strategy',
            'description': 'Momentum-based time-bin strategy',
            'parameters': {
                'lookback_period': {'type': 'integer', 'default': 20, 'min': 5, 'max': 100},
                'momentum_threshold': {'type': 'float', 'default': 0.02, 'min': 0.001, 'max': 0.1}
            },
            'supported_time_bins': 'all',
            'recommended_capital': 250000.0
        }
    ]
    
    return strategies


# Background task functions
async def _run_backtest_background(
    backtest_id: str,
    config: BacktestConfiguration,
    time_bins: List[TimeBin],
    strategy_params: Dict[str, Any],
    run_analysis: bool,
    analysis_types: List[AnalysisType]
):
    """Run backtest in background."""
    try:
        # Update status
        active_backtests[backtest_id]['status'] = 'RUNNING'
        active_backtests[backtest_id]['progress'] = 0.1
        
        # Run backtest
        result = await backtesting_engine.run_backtest(
            strategy_function=example_strategy_function,
            configuration=config,
            time_bins=time_bins,
            strategy_params=strategy_params
        )
        
        # Update progress
        active_backtests[backtest_id]['progress'] = 0.8
        
        # Store result
        completed_backtests[backtest_id] = result
        
        # Run analysis if requested
        if run_analysis and results_analyzer:
            active_backtests[backtest_id]['progress'] = 0.9
            
            analysis = await results_analyzer.analyze_comprehensive(
                result, analysis_types, cache_key=f"auto_{backtest_id}"
            )
            
            analysis_cache[f"auto_{backtest_id}"] = analysis
        
        # Mark as completed
        active_backtests[backtest_id]['status'] = 'COMPLETED'
        active_backtests[backtest_id]['progress'] = 1.0
        active_backtests[backtest_id]['completed_at'] = datetime.now()
        
        logger.info(f"Backtest {backtest_id} completed successfully")
        
    except Exception as e:
        # Mark as failed
        active_backtests[backtest_id]['status'] = 'FAILED'
        active_backtests[backtest_id]['error_message'] = str(e)
        logger.error(f"Backtest {backtest_id} failed: {str(e)}")


async def _run_analysis_background(
    analysis_id: str,
    backtest_id: str,
    analysis_types: List[AnalysisType],
    benchmark_results: List[BacktestResult],
    cache_results: bool
):
    """Run analysis in background."""
    try:
        backtest_result = completed_backtests[backtest_id]
        
        analysis = await results_analyzer.analyze_comprehensive(
            backtest_result,
            analysis_types,
            benchmark_results if benchmark_results else None,
            cache_key=analysis_id if cache_results else None
        )
        
        analysis_cache[analysis_id] = analysis
        
        logger.info(f"Analysis {analysis_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Analysis {analysis_id} failed: {str(e)}")


# Helper functions
def _convert_backtest_result_to_response(
    backtest_id: str,
    result: BacktestResult,
    include_trades: bool,
    include_daily_returns: bool
) -> BacktestResultResponse:
    """Convert internal backtest result to API response format."""
    
    def convert_period_result(period_result: BacktestPeriodResult) -> PeriodResultResponse:
        trades = None
        if include_trades:
            trades = [
                TradeResponse(
                    entry_time=trade.entry_time,
                    exit_time=trade.exit_time,
                    time_bin=TimeBinRequest(
                        account_name=trade.time_bin.account_name,
                        hour=trade.time_bin.hour,
                        minute_bin=trade.time_bin.minute_bin
                    ),
                    entry_price=trade.entry_price,
                    exit_price=trade.exit_price,
                    quantity=trade.quantity,
                    trade_type=trade.trade_type,
                    pnl=trade.pnl,
                    commission=trade.commission,
                    slippage=trade.slippage,
                    is_closed=trade.is_closed
                )
                for trade in period_result.trades
            ]
        
        daily_returns = period_result.daily_returns if include_daily_returns else None
        
        return PeriodResultResponse(
            start_date=period_result.start_date,
            end_date=period_result.end_date,
            initial_capital=period_result.initial_capital,
            final_capital=period_result.final_capital,
            total_return=period_result.total_return,
            num_trades=period_result.num_trades,
            winning_trades=period_result.winning_trades,
            losing_trades=period_result.losing_trades,
            avg_trade_pnl=period_result.avg_trade_pnl,
            max_drawdown=period_result.max_drawdown,
            sharpe_ratio=period_result.sharpe_ratio,
            sortino_ratio=period_result.sortino_ratio,
            profit_factor=period_result.profit_factor,
            win_rate=period_result.win_rate,
            total_commission=period_result.total_commission,
            total_slippage=period_result.total_slippage,
            trades=trades,
            daily_returns=daily_returns
        )
    
    # Convert configuration
    config_response = BacktestConfigRequest(
        start_date=result.configuration.start_date,
        end_date=result.configuration.end_date,
        initial_capital=result.configuration.initial_capital,
        commission_per_trade=result.configuration.commission_per_trade,
        slippage_bps=result.configuration.slippage_bps,
        method=BacktestMethodEnum(result.configuration.method.value),
        training_days=result.configuration.training_days,
        testing_days=result.configuration.testing_days,
        rebalance_frequency=result.configuration.rebalance_frequency,
        num_simulations=result.configuration.num_simulations,
        confidence_levels=result.configuration.confidence_levels,
        num_folds=result.configuration.num_folds,
        benchmark_symbol=result.configuration.benchmark_symbol,
        risk_free_rate=result.configuration.risk_free_rate
    )
    
    # Convert results
    overall_result = convert_period_result(result.overall_result)
    period_results = [convert_period_result(pr) for pr in result.period_results]
    
    # Convert method-specific results
    simulation_results = None
    if result.simulation_results:
        simulation_results = [convert_period_result(sr) for sr in result.simulation_results]
    
    out_of_sample_results = None
    if result.out_of_sample_results:
        out_of_sample_results = [convert_period_result(sr) for sr in result.out_of_sample_results]
    
    in_sample_results = None
    if result.in_sample_results:
        in_sample_results = [convert_period_result(sr) for sr in result.in_sample_results]
    
    fold_results = None
    if result.fold_results:
        fold_results = [convert_period_result(fr) for fr in result.fold_results]
    
    return BacktestResultResponse(
        backtest_id=backtest_id,
        configuration=config_response,
        method=BacktestMethodEnum(result.method.value),
        overall_result=overall_result,
        period_results=period_results,
        simulation_results=simulation_results,
        percentile_results=result.percentile_results,
        out_of_sample_results=out_of_sample_results,
        in_sample_results=in_sample_results,
        fold_results=fold_results,
        benchmark_comparison=result.benchmark_comparison,
        execution_time_seconds=result.execution_time_seconds,
        timestamp=result.timestamp
    )


def _convert_analysis_to_response(
    analysis_id: str,
    analysis: ComprehensiveAnalysis
) -> AnalysisResultResponse:
    """Convert internal analysis to API response format."""
    
    # Simplify complex analysis objects for API response
    performance_attribution = None
    if analysis.performance_attribution:
        pa = analysis.performance_attribution
        performance_attribution = {
            'best_time_bins': [{'time_bin': str(tb), 'contribution': contrib} for tb, contrib in pa.best_time_bins],
            'worst_time_bins': [{'time_bin': str(tb), 'contribution': contrib} for tb, contrib in pa.worst_time_bins],
            'consistency_score': pa.consistency_score,
            'reliability_score': pa.reliability_score
        }
    
    risk_decomposition = None
    if analysis.risk_decomposition:
        rd = analysis.risk_decomposition
        risk_decomposition = {
            'total_risk': rd.total_risk,
            'systematic_risk': rd.systematic_risk,
            'idiosyncratic_risk': rd.idiosyncratic_risk,
            'value_at_risk': rd.value_at_risk,
            'conditional_var': rd.conditional_var,
            'max_drawdown_analysis': rd.maximum_drawdown_analysis
        }
    
    trade_analysis = None
    if analysis.trade_analysis:
        ta = analysis.trade_analysis
        trade_analysis = {
            'trade_statistics': ta.trade_statistics,
            'win_loss_analysis': ta.win_loss_analysis,
            'trade_quality_score': ta.trade_quality_score,
            'execution_quality_score': ta.execution_quality_score
        }
    
    temporal_analysis = None
    if analysis.temporal_analysis:
        temp = analysis.temporal_analysis
        temporal_analysis = {
            'weekly_performance': temp.weekly_performance,
            'monthly_performance': temp.monthly_performance,
            'hourly_performance': temp.hourly_performance,
            'seasonal_patterns': temp.seasonal_patterns
        }
    
    statistical_validation = None
    if analysis.statistical_validation:
        sv = analysis.statistical_validation
        statistical_validation = {
            'significance_tests': sv.significance_tests,
            'distribution_analysis': sv.distribution_analysis,
            'overfitting_tests': sv.overfitting_tests
        }
    
    comparative_analysis = None
    if analysis.comparative_analysis:
        ca = analysis.comparative_analysis
        comparative_analysis = {
            'performance_rankings': ca.performance_rankings,
            'risk_adjusted_rankings': ca.risk_adjusted_rankings,
            'peer_analysis': ca.peer_analysis
        }
    
    sensitivity_analysis = None
    if analysis.sensitivity_analysis:
        sa = analysis.sensitivity_analysis
        sensitivity_analysis = {
            'parameter_stability': sa.parameter_stability,
            'robustness_score': sa.robustness_score,
            'stress_test_results': sa.stress_test_results
        }
    
    # Extract backtest ID from result (simplified)
    backtest_id = "unknown"  # Would extract from actual backtest result
    
    return AnalysisResultResponse(
        analysis_id=analysis_id,
        backtest_id=backtest_id,
        analysis_timestamp=analysis.analysis_timestamp,
        overall_quality_score=analysis.overall_quality_score,
        recommendation=analysis.recommendation,
        key_insights=analysis.key_insights,
        performance_attribution=performance_attribution,
        risk_decomposition=risk_decomposition,
        trade_analysis=trade_analysis,
        temporal_analysis=temporal_analysis,
        statistical_validation=statistical_validation,
        comparative_analysis=comparative_analysis,
        sensitivity_analysis=sensitivity_analysis
    )


# Service initialization functions
def initialize_backtesting_endpoints(
    engine: TimeBinBacktestingEngine,
    analyzer: BacktestResultsAnalyzer,
    tb_analyzer: TimeBinAnalyzer
):
    """
    Initialize backtesting endpoints with service instances.
    
    This function should be called during application startup to inject
    the required service dependencies.
    """
    global backtesting_engine, results_analyzer, time_bin_analyzer
    
    backtesting_engine = engine
    results_analyzer = analyzer
    time_bin_analyzer = tb_analyzer
    
    logger.info("Backtesting endpoints initialized with service dependencies")


def shutdown_backtesting_endpoints():
    """
    Shutdown backtesting endpoints and clean up resources.
    
    This function should be called during application shutdown.
    """
    global backtesting_engine, results_analyzer, time_bin_analyzer
    global active_backtests, completed_backtests, analysis_cache
    
    # Cancel any running backtests
    for backtest_id, info in active_backtests.items():
        if info['status'] in ['PENDING', 'RUNNING']:
            info['status'] = 'CANCELLED'
    
    # Clear caches
    active_backtests.clear()
    completed_backtests.clear()
    analysis_cache.clear()
    
    # Clear service references
    backtesting_engine = None
    results_analyzer = None
    time_bin_analyzer = None
    
    logger.info("Backtesting endpoints shut down")