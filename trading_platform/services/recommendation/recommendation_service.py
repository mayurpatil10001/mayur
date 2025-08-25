"""
Core recommendation service combining statistical, ML, and Monte Carlo analysis.

This service implements the main recommendation logic that combines all analysis
components to generate trading recommendations with multiple strategies and
time-based filtering.

Requirements: 6.1, 6.4
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import json

from ...models.trading import ProcessedTrade, TradingRecommendation, PerformanceMetrics
from ...interfaces.recommendation_interfaces import IRecommendationService
from ..performance_metrics_calculator import PerformanceMetricsCalculator
from ..temporal_analysis_service import TemporalAnalysisService, TemporalAnalysisResult
from ..machine_learning.prediction_service import PredictionService
from ..monte_carlo.monte_carlo_simulator import MonteCarloSimulator


class StrategyType(Enum):
    """Types of recommendation strategies."""
    STATISTICAL = "statistical"
    MACHINE_LEARNING = "machine_learning"
    MONTE_CARLO = "monte_carlo"
    ENSEMBLE = "ensemble"


@dataclass
class StrategyResult:
    """Result from a single strategy evaluation."""
    strategy_type: StrategyType
    recommendation: str  # 'TRADE' or 'AVOID'
    confidence_score: float
    expected_return: float
    expected_risk: float
    reasoning: str
    execution_time: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RecommendationContext:
    """Context information for generating recommendations."""
    account_name: str
    symbol: str
    current_time: datetime
    hour_of_day: int
    day_of_week: int
    historical_trades: List[ProcessedTrade]
    risk_tolerance: float = 0.5  # 0.0 (conservative) to 1.0 (aggressive)


@dataclass
class StrategyComparison:
    """Comparison between different strategies."""
    strategy_a: StrategyType
    strategy_b: StrategyType
    accuracy_difference: float
    return_difference: float
    risk_difference: float
    preference_score: float  # Higher means strategy_a is preferred
    sample_size: int
    comparison_timestamp: datetime = field(default_factory=datetime.now)


class RecommendationServiceError(Exception):
    """Exception raised by recommendation service."""
    pass


class RecommendationService(IRecommendationService):
    """
    Core recommendation service combining multiple analysis strategies.
    
    This service integrates statistical analysis, machine learning predictions,
    and Monte Carlo simulations to provide comprehensive trading recommendations
    with strategy comparison and time-based filtering.
    """
    
    def __init__(self, 
                 performance_calculator: Optional[PerformanceMetricsCalculator] = None,
                 temporal_analyzer: Optional[TemporalAnalysisService] = None,
                 prediction_service: Optional[PredictionService] = None,
                 monte_carlo_simulator: Optional[MonteCarloSimulator] = None,
                 enable_parallel_strategies: bool = True,
                 default_risk_tolerance: float = 0.5):
        """
        Initialize the recommendation service.
        
        Args:
            performance_calculator: Performance metrics calculator
            temporal_analyzer: Temporal analysis service
            prediction_service: ML prediction service
            monte_carlo_simulator: Monte Carlo simulator
            enable_parallel_strategies: Enable parallel strategy execution
            default_risk_tolerance: Default risk tolerance (0.0 to 1.0)
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize analysis components
        self.performance_calculator = performance_calculator or PerformanceMetricsCalculator()
        self.temporal_analyzer = temporal_analyzer or TemporalAnalysisService()
        self.prediction_service = prediction_service or PredictionService()
        self.monte_carlo_simulator = monte_carlo_simulator or MonteCarloSimulator()
        
        # Configuration
        self.enable_parallel_strategies = enable_parallel_strategies
        self.default_risk_tolerance = default_risk_tolerance
        
        # Strategy weights for ensemble
        self.strategy_weights = {
            StrategyType.STATISTICAL: 0.3,
            StrategyType.MACHINE_LEARNING: 0.4,
            StrategyType.MONTE_CARLO: 0.3
        }
        
        # Recommendation history for strategy comparison
        self.recommendation_history: List[Tuple[RecommendationContext, List[StrategyResult]]] = []
        self.strategy_comparisons: List[StrategyComparison] = []
        
        # Performance tracking
        self.strategy_performance: Dict[StrategyType, Dict[str, float]] = {
            strategy: {'accuracy': 0.0, 'total_recommendations': 0, 'correct_predictions': 0}
            for strategy in StrategyType
        }
    
    def generate_recommendation(self, context: RecommendationContext) -> TradingRecommendation:
        """
        Generate comprehensive trading recommendation using all strategies.
        
        Args:
            context: Recommendation context with account, symbol, and time info
            
        Returns:
            TradingRecommendation with final recommendation and reasoning
            
        Raises:
            RecommendationServiceError: If recommendation generation fails
        """
        if not context.historical_trades:
            raise RecommendationServiceError("No historical trades provided for recommendation")
        
        try:
            self.logger.info(f"Generating recommendation for {context.account_name} - {context.symbol} at {context.current_time}")
            
            # Execute all strategies
            if self.enable_parallel_strategies:
                strategy_results = self._execute_strategies_parallel(context)
            else:
                strategy_results = self._execute_strategies_sequential(context)
            
            # Combine strategies into final recommendation
            final_recommendation = self._combine_strategy_results(context, strategy_results)
            
            # Store in history for future analysis
            self.recommendation_history.append((context, strategy_results))
            
            # Update strategy performance tracking
            self._update_strategy_performance(strategy_results)
            
            return final_recommendation
            
        except Exception as e:
            self.logger.error(f"Failed to generate recommendation: {e}")
            raise RecommendationServiceError(f"Recommendation generation failed: {e}")
    
    def _execute_strategies_parallel(self, context: RecommendationContext) -> List[StrategyResult]:
        """Execute all strategies in parallel for better performance."""
        strategy_results = []
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all strategy executions
            future_to_strategy = {
                executor.submit(self._execute_statistical_strategy, context): StrategyType.STATISTICAL,
                executor.submit(self._execute_ml_strategy, context): StrategyType.MACHINE_LEARNING,
                executor.submit(self._execute_monte_carlo_strategy, context): StrategyType.MONTE_CARLO
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_strategy):
                strategy_type = future_to_strategy[future]
                try:
                    result = future.result()
                    strategy_results.append(result)
                except Exception as e:
                    self.logger.warning(f"Strategy {strategy_type.value} failed: {e}")
                    # Create fallback result
                    fallback_result = StrategyResult(
                        strategy_type=strategy_type,
                        recommendation='AVOID',
                        confidence_score=0.0,
                        expected_return=0.0,
                        expected_risk=1.0,
                        reasoning=f"Strategy failed: {str(e)}",
                        execution_time=0.0
                    )
                    strategy_results.append(fallback_result)
        
        return strategy_results
    
    def _execute_strategies_sequential(self, context: RecommendationContext) -> List[StrategyResult]:
        """Execute all strategies sequentially."""
        strategy_results = []
        
        # Execute each strategy
        strategies = [
            (self._execute_statistical_strategy, StrategyType.STATISTICAL),
            (self._execute_ml_strategy, StrategyType.MACHINE_LEARNING),
            (self._execute_monte_carlo_strategy, StrategyType.MONTE_CARLO)
        ]
        
        for strategy_func, strategy_type in strategies:
            try:
                result = strategy_func(context)
                strategy_results.append(result)
            except Exception as e:
                self.logger.warning(f"Strategy {strategy_type.value} failed: {e}")
                # Create fallback result
                fallback_result = StrategyResult(
                    strategy_type=strategy_type,
                    recommendation='AVOID',
                    confidence_score=0.0,
                    expected_return=0.0,
                    expected_risk=1.0,
                    reasoning=f"Strategy failed: {str(e)}",
                    execution_time=0.0
                )
                strategy_results.append(fallback_result)
        
        return strategy_results
    
    def _execute_statistical_strategy(self, context: RecommendationContext) -> StrategyResult:
        """Execute Strategy A: Pure statistical temporal patterns."""
        import time
        start_time = time.time()
        
        try:
            # Perform temporal analysis
            temporal_result = self.temporal_analyzer.analyze_temporal_patterns(
                trades=context.historical_trades,
                account_name=context.account_name,
                symbol=context.symbol
            )
            
            # Get recommendations based on current time
            recommendations = self.temporal_analyzer.get_trading_recommendations(
                temporal_result, context.current_time
            )
            
            # Calculate confidence based on statistical significance
            current_hour_pattern = next(
                (p for p in temporal_result.hourly_patterns if p.time_period == context.hour_of_day),
                None
            )
            current_day_pattern = next(
                (p for p in temporal_result.daily_patterns if p.time_period == context.day_of_week),
                None
            )
            
            # Determine recommendation
            hour_favorable = context.hour_of_day in temporal_result.best_hours
            day_favorable = context.day_of_week in temporal_result.best_days
            hour_unfavorable = context.hour_of_day in temporal_result.worst_hours
            day_unfavorable = context.day_of_week in temporal_result.worst_days
            
            if hour_favorable and day_favorable:
                recommendation = 'TRADE'
                confidence_score = 0.8
                expected_return = (current_hour_pattern.average_pnl + current_day_pattern.average_pnl) / 2 if current_hour_pattern and current_day_pattern else 0.0
                reasoning = "Both hour and day patterns are statistically favorable"
            elif hour_favorable or day_favorable:
                recommendation = 'TRADE'
                confidence_score = 0.6
                pattern = current_hour_pattern if hour_favorable else current_day_pattern
                expected_return = pattern.average_pnl if pattern else 0.0
                reasoning = "One temporal pattern is statistically favorable"
            elif hour_unfavorable and day_unfavorable:
                recommendation = 'AVOID'
                confidence_score = 0.8
                expected_return = (current_hour_pattern.average_pnl + current_day_pattern.average_pnl) / 2 if current_hour_pattern and current_day_pattern else 0.0
                reasoning = "Both hour and day patterns are statistically unfavorable"
            elif hour_unfavorable or day_unfavorable:
                recommendation = 'AVOID'
                confidence_score = 0.6
                pattern = current_hour_pattern if hour_unfavorable else current_day_pattern
                expected_return = pattern.average_pnl if pattern else 0.0
                reasoning = "One temporal pattern is statistically unfavorable"
            else:
                recommendation = 'AVOID'
                confidence_score = 0.3
                expected_return = 0.0
                reasoning = "No significant temporal patterns detected"
            
            # Calculate risk based on volatility
            hour_volatility = current_hour_pattern.volatility if current_hour_pattern else 0.0
            day_volatility = current_day_pattern.volatility if current_day_pattern else 0.0
            expected_risk = max(hour_volatility, day_volatility) / 100.0  # Normalize to 0-1 scale
            
            execution_time = time.time() - start_time
            
            return StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation=recommendation,
                confidence_score=confidence_score,
                expected_return=expected_return,
                expected_risk=expected_risk,
                reasoning=reasoning,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            raise RecommendationServiceError(f"Statistical strategy failed: {e}")
    
    def _execute_ml_strategy(self, context: RecommendationContext) -> StrategyResult:
        """Execute Strategy B: ML-enhanced predictions."""
        import time
        start_time = time.time()
        
        try:
            # Prepare features for ML prediction
            conditions = {
                'account': context.account_name,
                'symbol': context.symbol,
                'hour_of_day': context.hour_of_day,
                'day_of_week': context.day_of_week,
                'timestamp': context.current_time
            }
            
            # Get ML prediction
            prediction = self.prediction_service.predict_optimal_conditions(conditions)
            
            # Extract prediction metrics
            profit_probability = prediction.get('profit_probability', 0.5)
            expected_return = prediction.get('expected_return', 0.0)
            confidence_score = prediction.get('confidence_score', 0.0)
            risk_score = prediction.get('risk_score', 1.0)
            
            # Determine recommendation based on ML prediction
            if profit_probability > 0.6 and confidence_score > 0.7:
                recommendation = 'TRADE'
                reasoning = f"ML model predicts high profit probability ({profit_probability:.2f}) with good confidence ({confidence_score:.2f})"
            elif profit_probability > 0.55 and confidence_score > 0.8:
                recommendation = 'TRADE'
                reasoning = f"ML model predicts moderate profit probability ({profit_probability:.2f}) with high confidence ({confidence_score:.2f})"
            else:
                recommendation = 'AVOID'
                reasoning = f"ML model shows low profit probability ({profit_probability:.2f}) or confidence ({confidence_score:.2f})"
            
            execution_time = time.time() - start_time
            
            return StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation=recommendation,
                confidence_score=confidence_score,
                expected_return=expected_return,
                expected_risk=risk_score,
                reasoning=reasoning,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            raise RecommendationServiceError(f"ML strategy failed: {e}")
    
    def _execute_monte_carlo_strategy(self, context: RecommendationContext) -> StrategyResult:
        """Execute Strategy C: Risk-adjusted Monte Carlo optimization."""
        import time
        start_time = time.time()
        
        try:
            # Run Monte Carlo simulation
            simulation_result = self.monte_carlo_simulator.run_simulation(
                trades=context.historical_trades,
                num_simulations=1000,  # Reduced for faster execution
                time_horizon=30  # 30-day horizon
            )
            
            # Extract risk metrics
            risk_metrics = simulation_result['statistics']['risk_metrics']
            returns = simulation_result['statistics']['returns']
            
            # Calculate risk-adjusted recommendation
            probability_of_profit = risk_metrics['probability_of_profit']
            expected_return = returns['mean']
            sharpe_ratio = risk_metrics['sharpe_ratio']
            max_drawdown = abs(risk_metrics['max_drawdown'])
            
            # Risk-adjusted scoring
            risk_tolerance = context.risk_tolerance
            
            # Adjust thresholds based on risk tolerance
            profit_threshold = 0.5 + (0.1 * risk_tolerance)  # 0.5 to 0.6
            sharpe_threshold = 0.5 + (0.5 * risk_tolerance)  # 0.5 to 1.0
            drawdown_threshold = 0.2 - (0.1 * risk_tolerance)  # 0.2 to 0.1
            
            # Determine recommendation
            if (probability_of_profit > profit_threshold and 
                sharpe_ratio > sharpe_threshold and 
                max_drawdown < drawdown_threshold):
                recommendation = 'TRADE'
                confidence_score = min(0.9, probability_of_profit + sharpe_ratio * 0.2)
                reasoning = f"Monte Carlo shows favorable risk-return profile (P(profit)={probability_of_profit:.2f}, Sharpe={sharpe_ratio:.2f})"
            elif probability_of_profit > 0.6:  # High probability but poor risk metrics
                recommendation = 'TRADE'
                confidence_score = 0.6
                reasoning = f"Monte Carlo shows high profit probability ({probability_of_profit:.2f}) but elevated risk"
            else:
                recommendation = 'AVOID'
                confidence_score = 1.0 - probability_of_profit
                reasoning = f"Monte Carlo shows unfavorable risk-return profile (P(profit)={probability_of_profit:.2f})"
            
            # Risk score based on multiple factors
            expected_risk = (max_drawdown + (1.0 - probability_of_profit)) / 2
            
            execution_time = time.time() - start_time
            
            return StrategyResult(
                strategy_type=StrategyType.MONTE_CARLO,
                recommendation=recommendation,
                confidence_score=confidence_score,
                expected_return=expected_return,
                expected_risk=expected_risk,
                reasoning=reasoning,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            raise RecommendationServiceError(f"Monte Carlo strategy failed: {e}")
    
    def _combine_strategy_results(self, context: RecommendationContext, 
                                strategy_results: List[StrategyResult]) -> TradingRecommendation:
        """Combine multiple strategy results into final recommendation."""
        if not strategy_results:
            raise RecommendationServiceError("No strategy results to combine")
        
        # Calculate weighted scores
        trade_score = 0.0
        avoid_score = 0.0
        total_weight = 0.0
        
        combined_expected_return = 0.0
        combined_expected_risk = 0.0
        combined_confidence = 0.0
        
        reasoning_parts = []
        
        for result in strategy_results:
            strategy_weight = self.strategy_weights.get(result.strategy_type, 0.0)
            
            if strategy_weight > 0:
                total_weight += strategy_weight
                
                # Weight the scores
                if result.recommendation == 'TRADE':
                    trade_score += strategy_weight * result.confidence_score
                else:
                    avoid_score += strategy_weight * result.confidence_score
                
                # Weight the metrics
                combined_expected_return += strategy_weight * result.expected_return
                combined_expected_risk += strategy_weight * result.expected_risk
                combined_confidence += strategy_weight * result.confidence_score
                
                # Add to reasoning
                reasoning_parts.append(f"{result.strategy_type.value}: {result.reasoning}")
        
        # Normalize by total weight
        if total_weight > 0:
            combined_expected_return /= total_weight
            combined_expected_risk /= total_weight
            combined_confidence /= total_weight
        
        # Determine final recommendation
        if trade_score > avoid_score:
            final_action = 'TRADE'
            final_confidence = trade_score / total_weight if total_weight > 0 else 0.0
        else:
            final_action = 'AVOID'
            final_confidence = avoid_score / total_weight if total_weight > 0 else 0.0
        
        # Create comprehensive reasoning
        strategy_summary = f"Combined analysis from {len(strategy_results)} strategies. "
        strategy_details = " | ".join(reasoning_parts)
        final_reasoning = strategy_summary + strategy_details
        
        return TradingRecommendation(
            timestamp=context.current_time,
            account_name=context.account_name,
            symbol=context.symbol,
            recommended_action=final_action,
            confidence_score=final_confidence,
            expected_return=combined_expected_return,
            expected_risk=combined_expected_risk,
            reasoning=final_reasoning,
            hour_of_day=context.hour_of_day,
            day_of_week=context.day_of_week,
            historical_win_rate=max(0.0, min(1.0, 0.5 + combined_expected_return * 0.1)),  # Approximate
            avg_profit_this_time=combined_expected_return
        )
    
    def compare_strategies(self, lookback_days: int = 30) -> List[StrategyComparison]:
        """
        Compare performance of different strategies over recent history.
        
        Args:
            lookback_days: Number of days to look back for comparison
            
        Returns:
            List of strategy comparisons
        """
        if len(self.recommendation_history) < 10:
            self.logger.warning("Insufficient recommendation history for strategy comparison")
            return []
        
        # Filter recent recommendations
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_history = [
            (context, results) for context, results in self.recommendation_history
            if context.current_time >= cutoff_date
        ]
        
        if not recent_history:
            return []
        
        # Calculate strategy performance metrics
        strategy_metrics = {}
        for strategy_type in StrategyType:
            if strategy_type == StrategyType.ENSEMBLE:
                continue  # Skip ensemble for individual comparison
            
            strategy_results = []
            for context, results in recent_history:
                strategy_result = next((r for r in results if r.strategy_type == strategy_type), None)
                if strategy_result:
                    strategy_results.append(strategy_result)
            
            if strategy_results:
                accuracy = sum(1 for r in strategy_results if r.confidence_score > 0.5) / len(strategy_results)
                avg_return = np.mean([r.expected_return for r in strategy_results])
                avg_risk = np.mean([r.expected_risk for r in strategy_results])
                
                strategy_metrics[strategy_type] = {
                    'accuracy': accuracy,
                    'avg_return': avg_return,
                    'avg_risk': avg_risk,
                    'sample_size': len(strategy_results)
                }
        
        # Generate pairwise comparisons
        comparisons = []
        strategy_types = list(strategy_metrics.keys())
        
        for i, strategy_a in enumerate(strategy_types):
            for strategy_b in strategy_types[i+1:]:
                metrics_a = strategy_metrics[strategy_a]
                metrics_b = strategy_metrics[strategy_b]
                
                accuracy_diff = metrics_a['accuracy'] - metrics_b['accuracy']
                return_diff = metrics_a['avg_return'] - metrics_b['avg_return']
                risk_diff = metrics_a['avg_risk'] - metrics_b['avg_risk']
                
                # Calculate preference score (higher return, lower risk preferred)
                preference_score = return_diff - risk_diff + accuracy_diff * 0.5
                
                comparison = StrategyComparison(
                    strategy_a=strategy_a,
                    strategy_b=strategy_b,
                    accuracy_difference=accuracy_diff,
                    return_difference=return_diff,
                    risk_difference=risk_diff,
                    preference_score=preference_score,
                    sample_size=min(metrics_a['sample_size'], metrics_b['sample_size'])
                )
                
                comparisons.append(comparison)
        
        # Store comparisons
        self.strategy_comparisons.extend(comparisons)
        
        return comparisons
    
    def update_strategy_weights(self, performance_data: Dict[StrategyType, float]):
        """
        Update strategy weights based on recent performance.
        
        Args:
            performance_data: Dictionary mapping strategy types to performance scores
        """
        if not performance_data:
            return
        
        # Normalize performance scores
        total_performance = sum(performance_data.values())
        if total_performance <= 0:
            return
        
        # Update weights based on performance
        for strategy_type, performance in performance_data.items():
            if strategy_type in self.strategy_weights:
                new_weight = performance / total_performance
                # Smooth the update (moving average)
                self.strategy_weights[strategy_type] = (
                    0.7 * self.strategy_weights[strategy_type] + 0.3 * new_weight
                )
        
        # Ensure weights sum to 1.0
        total_weight = sum(self.strategy_weights.values())
        if total_weight > 0:
            for strategy_type in self.strategy_weights:
                self.strategy_weights[strategy_type] /= total_weight
        
        self.logger.info(f"Updated strategy weights: {self.strategy_weights}")
    
    def _update_strategy_performance(self, strategy_results: List[StrategyResult]):
        """Update internal strategy performance tracking."""
        for result in strategy_results:
            if result.strategy_type in self.strategy_performance:
                perf = self.strategy_performance[result.strategy_type]
                perf['total_recommendations'] += 1
                
                # Simple accuracy tracking based on confidence
                if result.confidence_score > 0.5:
                    perf['correct_predictions'] += 1
                
                # Update accuracy
                if perf['total_recommendations'] > 0:
                    perf['accuracy'] = perf['correct_predictions'] / perf['total_recommendations']
    
    def get_strategy_performance_summary(self) -> Dict[str, Any]:
        """
        Get summary of strategy performance.
        
        Returns:
            Dictionary with performance metrics for each strategy
        """
        summary = {}
        
        for strategy_type, perf in self.strategy_performance.items():
            summary[strategy_type.value] = {
                'accuracy': perf['accuracy'],
                'total_recommendations': perf['total_recommendations'],
                'current_weight': self.strategy_weights.get(strategy_type, 0.0)
            }
        
        summary['total_recommendations_generated'] = len(self.recommendation_history)
        summary['strategy_comparisons_performed'] = len(self.strategy_comparisons)
        
        return summary
    
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
        filtered = recommendations.copy()
        
        # Filter by hours
        if 'allowed_hours' in time_filters:
            allowed_hours = time_filters['allowed_hours']
            filtered = [r for r in filtered if r.hour_of_day in allowed_hours]
        
        # Filter by days of week
        if 'allowed_days' in time_filters:
            allowed_days = time_filters['allowed_days']
            filtered = [r for r in filtered if r.day_of_week in allowed_days]
        
        # Filter by minimum confidence
        if 'min_confidence' in time_filters:
            min_confidence = time_filters['min_confidence']
            filtered = [r for r in filtered if r.confidence_score >= min_confidence]
        
        # Filter by date range
        if 'start_date' in time_filters and 'end_date' in time_filters:
            start_date = time_filters['start_date']
            end_date = time_filters['end_date']
            filtered = [r for r in filtered if start_date <= r.timestamp <= end_date]
        
        return filtered