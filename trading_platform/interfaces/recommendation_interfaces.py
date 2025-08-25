"""
Interfaces for recommendation engine services.

This module defines the interfaces for recommendation services including
the main recommendation service and strategy evaluation components.

Requirements: 6.1, 6.4
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional, TYPE_CHECKING

from ..models.trading import ProcessedTrade, TradingRecommendation

if TYPE_CHECKING:
    from ..services.recommendation.recommendation_service import RecommendationContext, StrategyResult, StrategyComparison


class IRecommendationService(ABC):
    """Interface for the main recommendation service."""
    
    @abstractmethod
    def generate_recommendation(self, context: 'RecommendationContext') -> TradingRecommendation:
        """
        Generate comprehensive trading recommendation using all strategies.
        
        Args:
            context: Recommendation context with account, symbol, and time info
            
        Returns:
            TradingRecommendation with final recommendation and reasoning
        """
        pass
    
    @abstractmethod
    def compare_strategies(self, lookback_days: int = 30) -> List['StrategyComparison']:
        """
        Compare performance of different strategies over recent history.
        
        Args:
            lookback_days: Number of days to look back for comparison
            
        Returns:
            List of strategy comparisons
        """
        pass
    
    @abstractmethod
    def update_strategy_weights(self, performance_data: Dict[Any, float]):
        """
        Update strategy weights based on recent performance.
        
        Args:
            performance_data: Dictionary mapping strategy types to performance scores
        """
        pass
    
    @abstractmethod
    def filter_recommendations_by_time(self, 
                                     recommendations: List[TradingRecommendation],
                                     time_filters: Dict[str, Any]) -> List[TradingRecommendation]:
        """
        Filter recommendations based on time-based criteria.
        
        Args:
            recommendations: List of recommendations to filter
            time_filters: Dictionary with filtering criteria
            
        Returns:
            Filtered list of recommendations
        """
        pass
    
    @abstractmethod
    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """
        Get summary of strategy performance.
        
        Returns:
            Dictionary with performance metrics for each strategy
        """
        pass


class IStrategyEvaluator(ABC):
    """Interface for strategy evaluation and comparison."""
    
    @abstractmethod
    def evaluate_strategy_performance(self, 
                                    strategy_type: Any,
                                    recommendations: List[Any],
                                    actual_outcomes: Optional[List[float]] = None) -> Any:
        """
        Evaluate performance of a single strategy.
        
        Args:
            strategy_type: Type of strategy to evaluate
            recommendations: List of recommendations from the strategy
            actual_outcomes: Optional actual trade outcomes for validation
            
        Returns:
            Strategy performance metrics
        """
        pass
    
    @abstractmethod
    def compare_strategies(self, 
                         strategy_a: Any,
                         strategy_b: Any,
                         recommendations_a: List[Any],
                         recommendations_b: List[Any],
                         metrics_to_compare: Optional[List[str]] = None) -> List[Any]:
        """
        Compare two strategies across multiple metrics.
        
        Args:
            strategy_a: First strategy to compare
            strategy_b: Second strategy to compare
            recommendations_a: Recommendations from strategy A
            recommendations_b: Recommendations from strategy B
            metrics_to_compare: List of metrics to compare
            
        Returns:
            List of strategy comparison results
        """
        pass
    
    @abstractmethod
    def rank_strategies(self, 
                       strategy_performances: Dict[Any, Any],
                       ranking_criteria: str = 'composite') -> Any:
        """
        Rank strategies based on performance metrics.
        
        Args:
            strategy_performances: Dictionary of strategy performance metrics
            ranking_criteria: Criteria for ranking
            
        Returns:
            Strategy ranking results
        """
        pass


class IRiskOptimizer(ABC):
    """Interface for risk-return optimization."""
    
    @abstractmethod
    def optimize_single_recommendation(self, 
                                     trading_options: List[Any],
                                     risk_tolerance: Optional[float] = None,
                                     optimization_method: Optional[Any] = None) -> Any:
        """
        Optimize selection of single best trading option.
        
        Args:
            trading_options: List of available trading options
            risk_tolerance: Risk tolerance level (0.0 to 1.0)
            optimization_method: Optimization method to use
            
        Returns:
            Optimal trading option
        """
        pass
    
    @abstractmethod
    def optimize_portfolio_allocation(self, 
                                    trading_options: List[Any],
                                    risk_tolerance: Optional[float] = None,
                                    optimization_method: Optional[Any] = None,
                                    constraints: Optional[Any] = None) -> Any:
        """
        Optimize portfolio allocation across multiple accounts and assets.
        
        Args:
            trading_options: List of available trading options
            risk_tolerance: Risk tolerance level (0.0 to 1.0)
            optimization_method: Optimization method to use
            constraints: Optimization constraints
            
        Returns:
            OptimizationResult with optimal weights and metrics
        """
        pass
    
    @abstractmethod
    def get_risk_tolerance_parameters(self, risk_tolerance: float) -> Dict[str, Any]:
        """
        Get risk tolerance parameters for given risk level.
        
        Args:
            risk_tolerance: Risk tolerance level (0.0 to 1.0)
            
        Returns:
            Dictionary with risk tolerance parameters
        """
        pass
    
    @abstractmethod
    def validate_optimization_result(self, 
                                   result: Any,
                                   constraints: Any) -> bool:
        """
        Validate optimization result against constraints.
        
        Args:
            result: Optimization result to validate
            constraints: Constraints to validate against
            
        Returns:
            True if result satisfies constraints, False otherwise
        """
        pass