"""
Advanced Recommendation API endpoints integrating all sophisticated analytics.

This module provides REST endpoints for intelligent trading recommendations that combine:
- Time-bin analysis with statistical significance
- Monte Carlo risk assessment  
- Walk-Forward validation
- Market correlation analysis
- VIX regime analysis

Requirements: 1.6, 8.1-8.6, 12.1-12.6
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ..dependencies import (
    get_database_session,
    require_read_permission
)
from ..models.common import APIResponse
from ..exceptions import ServiceException

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for advanced recommendations
class AdvancedRecommendationResponse(BaseModel):
    """Advanced recommendation with full analytics integration"""
    timestamp: datetime
    time_bin: Dict[str, Any]
    action: str = Field(..., description="STRONG_BUY, BUY, HOLD, AVOID, STRONG_AVOID")
    confidence: str = Field(..., description="VERY_HIGH, HIGH, MEDIUM, LOW, VERY_LOW")
    
    # Core metrics
    expected_return: float
    probability_of_profit: float
    risk_score: float
    
    # Statistical validation
    statistical_significance: bool
    p_value: float
    confidence_interval: List[float]
    sample_size: int
    
    # Monte Carlo analysis
    var_95: float
    expected_shortfall: float
    worst_case_scenario: float
    best_case_scenario: float
    
    # Walk-forward validation
    out_of_sample_performance: float
    robustness_score: float
    performance_decay_rate: float
    
    # Market correlation
    market_correlation: float
    beta_coefficient: float
    alpha_generation: float
    market_neutrality: bool
    
    # VIX regime analysis
    current_vix_regime: str
    regime_performance: Dict[str, float]
    regime_preference: str
    
    # Reasoning and alerts
    reasoning: str
    alerts: List[str]
    recommendations: List[str]

class MarketConditionsResponse(BaseModel):
    """Current market conditions"""
    timestamp: datetime
    current_vix: float
    vix_regime: str
    current_spy: float
    market_trend: str

class RecommendationSummaryResponse(BaseModel):
    """Summary of recommendation analysis"""
    total_recommendations: int
    high_confidence_count: int
    buy_recommendations: int
    avoid_recommendations: int
    average_confidence: float
    market_conditions: MarketConditionsResponse


@router.get(
    "/advanced",
    response_model=APIResponse[List[AdvancedRecommendationResponse]],
    summary="Get advanced analytics recommendations",
    description="Get intelligent trading recommendations using Monte Carlo, Walk-Forward, Market Correlation, and VIX Regime Analysis."
)
async def get_advanced_recommendations(
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    min_confidence: float = Query(0.7, ge=0.0, le=1.0, description="Minimum confidence score (0.7 = HIGH confidence)"),
    include_market_context: bool = Query(True, description="Include market correlation and VIX regime analysis"),
    max_recommendations: int = Query(10, ge=1, le=50, description="Maximum number of recommendations to return"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[List[AdvancedRecommendationResponse]]:
    """
    Generate intelligent trading recommendations using all advanced analytics components.
    
    This endpoint integrates:
    - Time-bin analysis with statistical significance testing
    - Monte Carlo risk assessment with VaR and Expected Shortfall
    - Walk-Forward validation for strategy robustness
    - Market correlation analysis with SPY/QQQ benchmarks
    - VIX volatility regime analysis for market context
    """
    
    try:
        # Import the advanced recommendation engine
        from integrate_advanced_recommendations import AdvancedRecommendationEngine
        
        logger.info(f"Generating advanced recommendations for user {current_user.get('username', 'unknown')}")
        
        # Initialize the advanced recommendation engine
        engine = AdvancedRecommendationEngine(db)
        
        # Get accounts to analyze
        accounts = [account_name] if account_name else None
        
        # Generate intelligent recommendations
        advanced_recommendations = await engine.generate_intelligent_recommendations(
            current_time=datetime.now(),
            accounts=accounts,
            min_confidence=min_confidence
        )
        
        # Limit results
        advanced_recommendations = advanced_recommendations[:max_recommendations]
        
        # Convert to API response format
        api_recommendations = []
        for rec in advanced_recommendations:
            api_rec = AdvancedRecommendationResponse(
                timestamp=rec.timestamp,
                time_bin={
                    "account_name": rec.time_bin.account_name,
                    "hour": rec.time_bin.hour,
                    "minute_bin": rec.time_bin.minute_bin,
                    "day_of_week": rec.time_bin.day_of_week
                },
                action=rec.action.value,
                confidence=rec.confidence.value,
                
                # Core metrics
                expected_return=rec.expected_return,
                probability_of_profit=rec.probability_of_profit,
                risk_score=rec.risk_score,
                
                # Statistical validation
                statistical_significance=rec.statistical_significance,
                p_value=rec.p_value,
                confidence_interval=[rec.confidence_interval[0], rec.confidence_interval[1]],
                sample_size=rec.sample_size,
                
                # Monte Carlo analysis
                var_95=rec.var_95,
                expected_shortfall=rec.expected_shortfall,
                worst_case_scenario=rec.worst_case_scenario,
                best_case_scenario=rec.best_case_scenario,
                
                # Walk-forward validation
                out_of_sample_performance=rec.out_of_sample_performance,
                robustness_score=rec.robustness_score,
                performance_decay_rate=rec.performance_decay_rate,
                
                # Market correlation
                market_correlation=rec.market_correlation,
                beta_coefficient=rec.beta_coefficient,
                alpha_generation=rec.alpha_generation,
                market_neutrality=rec.market_neutrality,
                
                # VIX regime analysis
                current_vix_regime=rec.current_vix_regime,
                regime_performance=rec.regime_performance,
                regime_preference=rec.regime_preference,
                
                # Reasoning and alerts
                reasoning=rec.reasoning,
                alerts=rec.alerts,
                recommendations=rec.recommendations
            )
            
            api_recommendations.append(api_rec)
        
        logger.info(f"Generated {len(api_recommendations)} advanced recommendations")
        
        return APIResponse[List[AdvancedRecommendationResponse]](
            status="success",
            message=f"Generated {len(api_recommendations)} advanced analytics recommendations",
            data=api_recommendations
        )
        
    except ImportError as e:
        logger.error(f"Advanced recommendation engine not available: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Advanced analytics engine not available. Please ensure all analytics components are properly installed."
        )
        
    except ServiceException as e:
        logger.error(f"Service error in advanced recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
    except Exception as e:
        logger.error(f"Unexpected error generating advanced recommendations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate advanced recommendations: {str(e)}")


@router.get(
    "/market-conditions",
    response_model=APIResponse[MarketConditionsResponse],
    summary="Get current market conditions",
    description="Get current market conditions including VIX regime and SPY levels for recommendation context."
)
async def get_market_conditions(
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[MarketConditionsResponse]:
    """Get current market conditions for recommendation context."""
    
    try:
        from integrate_advanced_recommendations import AdvancedRecommendationEngine
        
        engine = AdvancedRecommendationEngine(db)
        market_conditions = await engine._get_current_market_conditions(datetime.now())
        
        conditions = MarketConditionsResponse(
            timestamp=market_conditions['timestamp'],
            current_vix=market_conditions['current_vix'],
            vix_regime=market_conditions['vix_regime'],
            current_spy=market_conditions['current_spy'],
            market_trend="bullish" if market_conditions['current_spy'] > 400 else "bearish"
        )
        
        return APIResponse[MarketConditionsResponse](
            status="success",
            message="Retrieved current market conditions",
            data=conditions
        )
        
    except Exception as e:
        logger.error(f"Error getting market conditions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get market conditions: {str(e)}")


@router.get(
    "/summary",
    response_model=APIResponse[RecommendationSummaryResponse],
    summary="Get recommendation summary",
    description="Get summary statistics of current advanced recommendations."
)
async def get_recommendation_summary(
    account_name: Optional[str] = Query(None, description="Filter by account name"),
    min_confidence: float = Query(0.6, ge=0.0, le=1.0, description="Minimum confidence score"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[RecommendationSummaryResponse]:
    """Get summary statistics of current recommendations."""
    
    try:
        from integrate_advanced_recommendations import AdvancedRecommendationEngine
        
        engine = AdvancedRecommendationEngine(db)
        
        # Get all recommendations
        accounts = [account_name] if account_name else None
        recommendations = await engine.generate_intelligent_recommendations(
            current_time=datetime.now(),
            accounts=accounts,
            min_confidence=0.0  # Get all recommendations for summary
        )
        
        # Get market conditions
        market_conditions = await engine._get_current_market_conditions(datetime.now())
        
        # Calculate summary statistics
        total_recommendations = len(recommendations)
        high_confidence_count = len([r for r in recommendations if r.confidence.value in ['HIGH', 'VERY_HIGH']])
        buy_recommendations = len([r for r in recommendations if r.action.value in ['BUY', 'STRONG_BUY']])
        avoid_recommendations = len([r for r in recommendations if r.action.value in ['AVOID', 'STRONG_AVOID']])
        
        confidence_scores = {
            'VERY_HIGH': 0.95, 'HIGH': 0.85, 'MEDIUM': 0.70, 'LOW': 0.55, 'VERY_LOW': 0.30
        }
        average_confidence = sum(confidence_scores[r.confidence.value] for r in recommendations) / max(total_recommendations, 1)
        
        summary = RecommendationSummaryResponse(
            total_recommendations=total_recommendations,
            high_confidence_count=high_confidence_count,
            buy_recommendations=buy_recommendations,
            avoid_recommendations=avoid_recommendations,
            average_confidence=average_confidence,
            market_conditions=MarketConditionsResponse(
                timestamp=market_conditions['timestamp'],
                current_vix=market_conditions['current_vix'],
                vix_regime=market_conditions['vix_regime'],
                current_spy=market_conditions['current_spy'],
                market_trend="bullish" if market_conditions['current_spy'] > 400 else "bearish"
            )
        )
        
        return APIResponse[RecommendationSummaryResponse](
            status="success",
            message="Retrieved recommendation summary",
            data=summary
        )
        
    except Exception as e:
        logger.error(f"Error getting recommendation summary: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recommendation summary: {str(e)}")


@router.post(
    "/refresh",
    response_model=APIResponse[Dict[str, Any]],
    summary="Refresh recommendations",
    description="Trigger a refresh of all advanced analytics and regenerate recommendations."
)
async def refresh_recommendations(
    background_tasks: BackgroundTasks,
    force_refresh: bool = Query(False, description="Force refresh of all cached analytics"),
    db: Session = Depends(get_database_session),
    current_user: dict = Depends(require_read_permission)
) -> APIResponse[Dict[str, Any]]:
    """Trigger a refresh of advanced analytics and recommendations."""
    
    try:
        def refresh_analytics():
            """Background task to refresh analytics"""
            logger.info("Starting background refresh of advanced analytics")
            # This would trigger refresh of cached analytics, market data, etc.
            # Implementation would depend on your caching strategy
            
        background_tasks.add_task(refresh_analytics)
        
        return APIResponse[Dict[str, Any]](
            status="success",
            message="Recommendation refresh initiated",
            data={
                "refresh_initiated": True,
                "timestamp": datetime.now(),
                "force_refresh": force_refresh
            }
        )
        
    except Exception as e:
        logger.error(f"Error initiating recommendation refresh: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initiate refresh: {str(e)}")