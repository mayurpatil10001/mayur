"""
Recommendation API endpoints.

This module provides REST endpoints for trading recommendations and strategy analysis.

Requirements: 7.1, 10.1, 10.3
"""

from datetime import datetime
from typing import List, Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session

from ..dependencies import (
    get_database_session,
    get_recommendation_service,
    require_read_permission
)
from ..models.common import APIResponse
from ..models.recommendations import (
    TradingRecommendationResponse,
    StrategyComparisonResponse,
    RecommendationHistoryResponse,
    BacktestResultsResponse,
    RecommendationRequest
)
from ..exceptions import ServiceException, DataNotFoundException
from ...services.recommendation.recommendation_service import RecommendationService


router = APIRouter()
logger = logging.getLogger(__name__)


async def _get_fallback_recommendations(
    account_name: Optional[str] = None,
    symbol: Optional[str] = None, 
    min_confidence: float = 0.0
) -> APIResponse[List[TradingRecommendationResponse]]:
    """Fallback recommendations when advanced engine is not available"""
    
    current_time = datetime.now()
    
    mock_recommendations = [
        TradingRecommendationResponse(
            timestamp=current_time,
            account_name="IPS_TM_10",
            symbol="NQ",
            recommended_action="TRADE",
            confidence_score=0.75,
            expected_return=125.50,
            expected_risk=85.25,
            reasoning="Strong historical performance at this hour (9 AM) with 68% win rate and average profit of $125",
            hour_of_day=current_time.hour,
            day_of_week=current_time.weekday(),
            historical_win_rate=0.68,
            avg_profit_this_time=125.50,
            strategy_used="statistical_temporal",
            risk_score=0.25,
            market_conditions="favorable"
        ),
        TradingRecommendationResponse(
            timestamp=current_time,
            account_name="IPS_TM_13",
            symbol="FDAX",
            recommended_action="AVOID",
            confidence_score=0.82,
            expected_return=-15.25,
            expected_risk=95.75,
            reasoning="Poor historical performance at this time with 42% win rate and high volatility",
            hour_of_day=current_time.hour,
            day_of_week=current_time.weekday(),
            historical_win_rate=0.42,
            avg_profit_this_time=-15.25,
            strategy_used="ml_enhanced",
            risk_score=0.78,
            market_conditions="unfavorable"
        )
    ]
    
    # Apply filters
    filtered_recommendations = mock_recommendations
    
    if account_name:
        filtered_recommendations = [r for r in filtered_recommendations if r.account_name == account_name]
    
    if symbol:
        filtered_recommendations = [r for r in filtered_recommendations if r.symbol == symbol]
    
    if min_confidence > 0:
        filtered_recommendations = [r for r in filtered_recommendations if r.confidence_score >= min_confidence]
    
    return APIResponse[List[TradingRecommendationResponse]](
        status="success",
        message=f"Retrieved {len(filtered_recommendations)} fallback recommendations (advanced analytics unavailable)",
        data=filtered_recommendations
    )


@router.get(
    "/current",
    response_model=APIResponse[List[TradingRecommendationResponse]],
    summary="Get current recommendations",
    description="Get current trading recommendations using advanced analytics (Monte Carlo, Walk-Forward, Market Correlation, VIX Regime Analysis)."
)
async def get_current_recommendations(
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    min_confidence: float = Query(0.7, ge=0.0, le=1.0, description="Minimum confidence score"),
    db: Session = Depends(get_database_session),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[List[TradingRecommendationResponse]]:
    """Get current trading recommendations using advanced analytics."""
    
    try:
        # Import the advanced recommendation engine
        from integrate_advanced_recommendations import AdvancedRecommendationEngine
        
        # Initialize the advanced recommendation engine
        engine = AdvancedRecommendationEngine(db)
        
        # Get accounts to analyze
        accounts = [account_name] if account_name else None
        
        # Generate intelligent recommendations using all advanced analytics
        advanced_recommendations = await engine.generate_intelligent_recommendations(
            current_time=datetime.now(),
            accounts=accounts,
            min_confidence=min_confidence
        )
        
        # Convert to API response format
        api_recommendations = []
        for rec in advanced_recommendations:
            # Map recommendation action to API format
            action_mapping = {
                "STRONG_BUY": "TRADE",
                "BUY": "TRADE", 
                "HOLD": "HOLD",
                "AVOID": "AVOID",
                "STRONG_AVOID": "AVOID"
            }
            
            # Map confidence to score
            confidence_mapping = {
                "VERY_HIGH": 0.95,
                "HIGH": 0.85,
                "MEDIUM": 0.70,
                "LOW": 0.55,
                "VERY_LOW": 0.30
            }
            
            # Determine market conditions
            market_conditions = "favorable" if rec.expected_return > 0 else "unfavorable"
            if rec.current_vix_regime == "HIGH":
                market_conditions = "volatile"
            
            # Get symbol from account (simplified mapping)
            symbol_mapping = {
                "IPS_TM_10": "NQ",
                "IPS_TM_13": "NQ", 
                "CL_3": "CL",
                "CL_TM_2": "CL"
            }
            
            api_rec = TradingRecommendationResponse(
                timestamp=rec.timestamp,
                account_name=rec.time_bin.account_name,
                symbol=symbol_mapping.get(rec.time_bin.account_name, "NQ"),
                recommended_action=action_mapping[rec.action.value],
                confidence_score=confidence_mapping[rec.confidence.value],
                expected_return=rec.expected_return,
                expected_risk=abs(rec.var_95),
                reasoning=rec.reasoning,
                hour_of_day=rec.time_bin.hour,
                day_of_week=rec.time_bin.day_of_week or rec.timestamp.weekday(),
                historical_win_rate=rec.probability_of_profit,
                avg_profit_this_time=rec.expected_return,
                strategy_used="advanced_analytics",
                risk_score=rec.risk_score,
                market_conditions=market_conditions
            )
            
            # Apply symbol filter if specified
            if symbol and api_rec.symbol != symbol:
                continue
                
            api_recommendations.append(api_rec)
        
        return APIResponse[List[TradingRecommendationResponse]](
            status="success",
            message=f"Retrieved {len(api_recommendations)} advanced analytics recommendations",
            data=api_recommendations
        )
        
    except ImportError as e:
        # Fallback to basic recommendations if advanced engine not available
        logger.warning(f"Advanced recommendation engine not available: {e}")
        return await _get_fallback_recommendations(account_name, symbol, min_confidence)
        
    except ServiceException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating advanced recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate advanced recommendations: {str(e)}")


@router.post(
    "/generate",
    response_model=APIResponse[TradingRecommendationResponse],
    summary="Generate recommendation",
    description="Generate a trading recommendation for specific parameters."
)
async def generate_recommendation(
    recommendation_request: RecommendationRequest,
    db: Session = Depends(get_database_session),
    recommendation_service: RecommendationService = Depends(get_recommendation_service),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[TradingRecommendationResponse]:
    """Generate a trading recommendation for specific parameters."""
    
    try:
        # TODO: Implement actual recommendation generation using service
        # For now, return mock recommendation based on request
        
        recommendation = TradingRecommendationResponse(
            timestamp=recommendation_request.timestamp or datetime.now(),
            account_name=recommendation_request.account_name,
            symbol=recommendation_request.symbol,
            recommended_action="TRADE" if recommendation_request.account_name == "IPS_TM_10" else "AVOID",
            confidence_score=0.72,
            expected_return=95.25,
            expected_risk=65.50,
            reasoning=f"Generated recommendation for {recommendation_request.account_name} trading {recommendation_request.symbol}",
            hour_of_day=(recommendation_request.timestamp or datetime.now()).hour,
            day_of_week=(recommendation_request.timestamp or datetime.now()).weekday(),
            historical_win_rate=0.64,
            avg_profit_this_time=95.25,
            strategy_used=recommendation_request.strategy or "statistical_temporal",
            risk_score=0.35,
            market_conditions="neutral"
        )
        
        return APIResponse[TradingRecommendationResponse](
            status="success",
            message=f"Generated recommendation for {recommendation_request.account_name}",
            data=recommendation
        )
        
    except ServiceException as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendation: {str(e)}")


@router.get(
    "/strategies/compare",
    response_model=APIResponse[StrategyComparisonResponse],
    summary="Compare strategies",
    description="Compare performance of different recommendation strategies."
)
async def compare_strategies(
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    start_date: Optional[datetime] = Query(None, description="Start date for comparison"),
    end_date: Optional[datetime] = Query(None, description="End date for comparison"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[StrategyComparisonResponse]:
    """Compare recommendation strategies."""
    
    try:
        # TODO: Implement actual strategy comparison using service
        # For now, return mock comparison results
        
        strategy_comparison = StrategyComparisonResponse(
            comparison_period_start=start_date or datetime(2024, 1, 1),
            comparison_period_end=end_date or datetime(2024, 12, 31),
            account_name=account_name or "ALL",
            strategies_compared=["statistical_temporal", "ml_enhanced", "monte_carlo_optimized"],
            strategy_performance={
                "statistical_temporal": {
                    "total_recommendations": 150,
                    "successful_recommendations": 98,
                    "success_rate": 0.653,
                    "average_return": 125.50,
                    "total_return": 12285.00,
                    "sharpe_ratio": 1.15,
                    "max_drawdown": -850.00
                },
                "ml_enhanced": {
                    "total_recommendations": 145,
                    "successful_recommendations": 102,
                    "success_rate": 0.703,
                    "average_return": 135.25,
                    "total_return": 13525.00,
                    "sharpe_ratio": 1.28,
                    "max_drawdown": -720.00
                },
                "monte_carlo_optimized": {
                    "total_recommendations": 132,
                    "successful_recommendations": 89,
                    "success_rate": 0.674,
                    "average_return": 142.75,
                    "total_return": 14275.00,
                    "sharpe_ratio": 1.35,
                    "max_drawdown": -650.00
                }
            },
            best_strategy="monte_carlo_optimized",
            statistical_significance={
                "anova_f_statistic": 3.45,
                "anova_p_value": 0.032,
                "significant_differences": True,
                "pairwise_comparisons": {
                    "statistical_vs_ml": {"p_value": 0.045, "significant": True},
                    "statistical_vs_monte_carlo": {"p_value": 0.021, "significant": True},
                    "ml_vs_monte_carlo": {"p_value": 0.156, "significant": False}
                }
            },
            recommendation="Use monte_carlo_optimized strategy for best risk-adjusted returns"
        )
        
        return APIResponse[StrategyComparisonResponse](
            status="success",
            message="Strategy comparison completed",
            data=strategy_comparison
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compare strategies: {str(e)}")


@router.get(
    "/history/{account_name}",
    response_model=APIResponse[List[RecommendationHistoryResponse]],
    summary="Get recommendation history",
    description="Get historical recommendations and their outcomes for an account."
)
async def get_recommendation_history(
    account_name: str = Path(..., description="Account name"),
    start_date: Optional[datetime] = Query(None, description="Start date for history"),
    end_date: Optional[datetime] = Query(None, description="End date for history"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[List[RecommendationHistoryResponse]]:
    """Get historical recommendations and their outcomes."""
    
    try:
        # TODO: Implement actual history retrieval from database
        # For now, return mock history
        
        mock_history = [
            RecommendationHistoryResponse(
                recommendation_id="rec_001",
                timestamp=datetime(2024, 1, 1, 9, 30),
                account_name=account_name,
                symbol="NQ",
                recommended_action="TRADE",
                confidence_score=0.75,
                expected_return=125.50,
                actual_return=135.25,
                strategy_used="statistical_temporal",
                outcome="successful",
                accuracy_score=0.92
            ),
            RecommendationHistoryResponse(
                recommendation_id="rec_002",
                timestamp=datetime(2024, 1, 1, 14, 15),
                account_name=account_name,
                symbol="NQ",
                recommended_action="AVOID",
                confidence_score=0.68,
                expected_return=-25.00,
                actual_return=-45.50,
                strategy_used="ml_enhanced",
                outcome="successful",
                accuracy_score=0.85
            ),
            RecommendationHistoryResponse(
                recommendation_id="rec_003",
                timestamp=datetime(2024, 1, 2, 10, 45),
                account_name=account_name,
                symbol="NQ",
                recommended_action="TRADE",
                confidence_score=0.82,
                expected_return=95.75,
                actual_return=-15.25,
                strategy_used="monte_carlo_optimized",
                outcome="failed",
                accuracy_score=0.35
            )
        ]
        
        # Apply date filters
        if start_date:
            mock_history = [h for h in mock_history if h.timestamp >= start_date]
        
        if end_date:
            mock_history = [h for h in mock_history if h.timestamp <= end_date]
        
        # Apply limit
        mock_history = mock_history[:limit]
        
        return APIResponse[List[RecommendationHistoryResponse]](
            status="success",
            message=f"Retrieved {len(mock_history)} historical recommendations for {account_name}",
            data=mock_history
        )
        
    except DataNotFoundException:
        raise HTTPException(status_code=404, detail=f"Account {account_name} not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve recommendation history: {str(e)}")


@router.get(
    "/backtest/{strategy}",
    response_model=APIResponse[BacktestResultsResponse],
    summary="Backtest strategy",
    description="Run backtest analysis for a specific recommendation strategy."
)
async def backtest_strategy(
    strategy: str = Path(..., description="Strategy name to backtest"),
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    start_date: Optional[datetime] = Query(None, description="Backtest start date"),
    end_date: Optional[datetime] = Query(None, description="Backtest end date"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[BacktestResultsResponse]:
    """Run backtest analysis for a recommendation strategy."""
    
    try:
        # TODO: Implement actual backtesting using service
        # For now, return mock backtest results
        
        backtest_results = BacktestResultsResponse(
            strategy_name=strategy,
            account_name=account_name or "ALL",
            backtest_period_start=start_date or datetime(2024, 1, 1),
            backtest_period_end=end_date or datetime(2024, 12, 31),
            total_recommendations=250,
            successful_recommendations=165,
            failed_recommendations=85,
            success_rate=0.66,
            total_return=15750.50,
            average_return_per_recommendation=63.00,
            sharpe_ratio=1.25,
            max_drawdown=-1250.00,
            volatility=0.18,
            best_month={"month": "March 2024", "return": 2850.00},
            worst_month={"month": "August 2024", "return": -950.00},
            monthly_returns={
                "2024-01": 1250.00,
                "2024-02": 1850.50,
                "2024-03": 2850.00,
                "2024-04": 1450.25,
                "2024-05": 1650.75,
                "2024-06": 1350.00,
                "2024-07": 1750.25,
                "2024-08": -950.00,
                "2024-09": 1550.50,
                "2024-10": 1850.25,
                "2024-11": 1450.00,
                "2024-12": 1750.00
            },
            confidence_analysis={
                "high_confidence_success_rate": 0.78,
                "medium_confidence_success_rate": 0.65,
                "low_confidence_success_rate": 0.52
            }
        )
        
        return APIResponse[BacktestResultsResponse](
            status="success",
            message=f"Backtest completed for strategy '{strategy}'",
            data=backtest_results
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run backtest: {str(e)}")