"""
Strategy evaluation and comparison framework.

This service provides comprehensive evaluation and comparison of different
recommendation strategies including performance tracking and statistical testing.

Requirements: 6.1, 6.4
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
import scipy.stats as stats
from collections import defaultdict

from ...models.trading import ProcessedTrade, TradingRecommendation
from .recommendation_service import StrategyType, StrategyResult, RecommendationContext


@dataclass
class StrategyPerformanceMetrics:
    """Performance metrics for a single strategy."""
    strategy_type: StrategyType
    total_recommendations: int
    correct_predictions: int
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    average_confidence: float
    average_expected_return: float
    average_expected_risk: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    evaluation_period_start: datetime
    evaluation_period_end: datetime
    sample_trades: int


@dataclass
class StrategyComparisonResult:
    """Result of comparing two strategies."""
    strategy_a: StrategyType
    strategy_b: StrategyType
    metric_name: str
    strategy_a_value: float
    strategy_b_value: float
    difference: float
    percentage_difference: float
    statistical_significance: float  # p-value
    is_significant: bool
    confidence_interval_lower: float
    confidence_interval_upper: float
    sample_size: int
    test_statistic: float
    comparison_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyRanking:
    """Ranking of strategies by performance."""
    rankings: List[Tuple[StrategyType, float]]  # (strategy, score)
    ranking_criteria: str
    evaluation_period: Tuple[datetime, datetime]
    total_strategies: int
    ranking_timestamp: datetime = field(default_factory=datetime.now)


class StrategyEvaluatorError(Exception):
    """Exception raised by strategy evaluator."""
    pass


class StrategyEvaluator:
    """
    Evaluates and compares recommendation strategy performance.
    
    This service provides comprehensive evaluation of different recommendation
    strategies including statistical testing, performance metrics, and rankings.
    """
    
    def __init__(self, significance_threshold: float = 0.05, confidence_level: float = 0.95):
        """
        Initialize the strategy evaluator.
        
        Args:
            significance_threshold: P-value threshold for statistical significance
            confidence_level: Confidence level for statistical tests
        """
        self.logger = logging.getLogger(__name__)
        self.significance_threshold = significance_threshold
        self.confidence_level = confidence_level
        
        # Performance tracking
        self.strategy_history: Dict[StrategyType, List[Tuple[RecommendationContext, StrategyResult, Optional[float]]]] = defaultdict(list)
        self.comparison_history: List[StrategyComparisonResult] = []
        self.ranking_history: List[StrategyRanking] = []
    
    def evaluate_strategy_performance(self, 
                                    strategy_type: StrategyType,
                                    recommendations: List[Tuple[RecommendationContext, StrategyResult]],
                                    actual_outcomes: Optional[List[float]] = None) -> StrategyPerformanceMetrics:
        """
        Evaluate performance of a single strategy.
        
        Args:
            strategy_type: Type of strategy to evaluate
            recommendations: List of (context, result) tuples
            actual_outcomes: Optional actual trade outcomes for validation
            
        Returns:
            StrategyPerformanceMetrics with comprehensive performance data
            
        Raises:
            StrategyEvaluatorError: If evaluation fails
        """
        if not recommendations:
            raise StrategyEvaluatorError(f"No recommendations provided for {strategy_type.value}")
        
        try:
            # Extract strategy results
            strategy_results = [result for context, result in recommendations if result.strategy_type == strategy_type]
            
            if not strategy_results:
                raise StrategyEvaluatorError(f"No results found for strategy {strategy_type.value}")
            
            # Basic metrics
            total_recommendations = len(strategy_results)
            trade_recommendations = sum(1 for r in strategy_results if r.recommendation == 'TRADE')
            avoid_recommendations = total_recommendations - trade_recommendations
            
            # Calculate accuracy if actual outcomes are provided
            if actual_outcomes and len(actual_outcomes) == len(strategy_results):
                correct_predictions = self._calculate_correct_predictions(strategy_results, actual_outcomes)
                accuracy = correct_predictions / total_recommendations if total_recommendations > 0 else 0.0
                
                # Calculate precision, recall, F1
                precision, recall, f1_score = self._calculate_classification_metrics(
                    strategy_results, actual_outcomes
                )
            else:
                # Use confidence-based approximation
                correct_predictions = sum(1 for r in strategy_results if r.confidence_score > 0.6)
                accuracy = correct_predictions / total_recommendations if total_recommendations > 0 else 0.0
                precision = recall = f1_score = accuracy  # Approximation
            
            # Confidence and return metrics
            average_confidence = np.mean([r.confidence_score for r in strategy_results])
            average_expected_return = np.mean([r.expected_return for r in strategy_results])
            average_expected_risk = np.mean([r.expected_risk for r in strategy_results])
            
            # Risk-adjusted metrics
            returns = [r.expected_return for r in strategy_results]
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            max_drawdown = self._calculate_max_drawdown(returns)
            
            # Trading metrics
            positive_returns = [r for r in returns if r > 0]
            negative_returns = [r for r in returns if r <= 0]
            
            win_rate = len(positive_returns) / len(returns) if returns else 0.0
            
            gross_profit = sum(positive_returns) if positive_returns else 0.0
            gross_loss = abs(sum(negative_returns)) if negative_returns else 0.0
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf') if gross_profit > 0 else 0.0
            
            # Evaluation period
            contexts = [context for context, result in recommendations]
            evaluation_period_start = min(c.current_time for c in contexts)
            evaluation_period_end = max(c.current_time for c in contexts)
            
            # Sample trades count
            sample_trades = sum(len(c.historical_trades) for c in contexts) // len(contexts) if contexts else 0
            
            return StrategyPerformanceMetrics(
                strategy_type=strategy_type,
                total_recommendations=total_recommendations,
                correct_predictions=correct_predictions,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                average_confidence=average_confidence,
                average_expected_return=average_expected_return,
                average_expected_risk=average_expected_risk,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                win_rate=win_rate,
                profit_factor=profit_factor,
                evaluation_period_start=evaluation_period_start,
                evaluation_period_end=evaluation_period_end,
                sample_trades=sample_trades
            )
            
        except Exception as e:
            raise StrategyEvaluatorError(f"Failed to evaluate strategy {strategy_type.value}: {e}")
    
    def compare_strategies(self, 
                         strategy_a: StrategyType,
                         strategy_b: StrategyType,
                         recommendations_a: List[Tuple[RecommendationContext, StrategyResult]],
                         recommendations_b: List[Tuple[RecommendationContext, StrategyResult]],
                         metrics_to_compare: Optional[List[str]] = None) -> List[StrategyComparisonResult]:
        """
        Compare two strategies across multiple metrics.
        
        Args:
            strategy_a: First strategy to compare
            strategy_b: Second strategy to compare
            recommendations_a: Recommendations from strategy A
            recommendations_b: Recommendations from strategy B
            metrics_to_compare: List of metrics to compare
            
        Returns:
            List of StrategyComparisonResult objects
            
        Raises:
            StrategyEvaluatorError: If comparison fails
        """
        if not recommendations_a or not recommendations_b:
            raise StrategyEvaluatorError("Both strategies must have recommendations for comparison")
        
        if metrics_to_compare is None:
            metrics_to_compare = ['accuracy', 'expected_return', 'confidence_score', 'expected_risk']
        
        try:
            # Get performance metrics for both strategies
            metrics_a = self.evaluate_strategy_performance(strategy_a, recommendations_a)
            metrics_b = self.evaluate_strategy_performance(strategy_b, recommendations_b)
            
            # Extract data for statistical testing
            results_a = [result for context, result in recommendations_a if result.strategy_type == strategy_a]
            results_b = [result for context, result in recommendations_b if result.strategy_type == strategy_b]
            
            comparisons = []
            
            for metric_name in metrics_to_compare:
                # Get metric values
                values_a = self._extract_metric_values(results_a, metric_name)
                values_b = self._extract_metric_values(results_b, metric_name)
                
                if not values_a or not values_b:
                    self.logger.warning(f"Insufficient data for metric {metric_name}")
                    continue
                
                # Calculate basic statistics
                mean_a = np.mean(values_a)
                mean_b = np.mean(values_b)
                difference = mean_a - mean_b
                percentage_difference = (difference / mean_b * 100) if mean_b != 0 else 0.0
                
                # Perform statistical test
                if len(values_a) > 1 and len(values_b) > 1:
                    test_stat, p_value = stats.ttest_ind(values_a, values_b, equal_var=False)
                    is_significant = p_value < self.significance_threshold
                    
                    # Calculate confidence interval for the difference
                    ci_lower, ci_upper = self._calculate_difference_confidence_interval(values_a, values_b)
                else:
                    test_stat = 0.0
                    p_value = 1.0
                    is_significant = False
                    ci_lower = ci_upper = difference
                
                comparison = StrategyComparisonResult(
                    strategy_a=strategy_a,
                    strategy_b=strategy_b,
                    metric_name=metric_name,
                    strategy_a_value=mean_a,
                    strategy_b_value=mean_b,
                    difference=difference,
                    percentage_difference=percentage_difference,
                    statistical_significance=p_value,
                    is_significant=is_significant,
                    confidence_interval_lower=ci_lower,
                    confidence_interval_upper=ci_upper,
                    sample_size=min(len(values_a), len(values_b)),
                    test_statistic=test_stat
                )
                
                comparisons.append(comparison)
            
            # Store in history
            self.comparison_history.extend(comparisons)
            
            return comparisons
            
        except Exception as e:
            raise StrategyEvaluatorError(f"Failed to compare strategies: {e}")
    
    def rank_strategies(self, 
                       strategy_performances: Dict[StrategyType, StrategyPerformanceMetrics],
                       ranking_criteria: str = 'composite') -> StrategyRanking:
        """
        Rank strategies based on performance metrics.
        
        Args:
            strategy_performances: Dictionary of strategy performance metrics
            ranking_criteria: Criteria for ranking ('accuracy', 'return', 'sharpe', 'composite')
            
        Returns:
            StrategyRanking with ordered strategy rankings
            
        Raises:
            StrategyEvaluatorError: If ranking fails
        """
        if not strategy_performances:
            raise StrategyEvaluatorError("No strategy performances provided for ranking")
        
        try:
            rankings = []
            
            for strategy_type, metrics in strategy_performances.items():
                if ranking_criteria == 'accuracy':
                    score = metrics.accuracy
                elif ranking_criteria == 'return':
                    score = metrics.average_expected_return
                elif ranking_criteria == 'sharpe':
                    score = metrics.sharpe_ratio
                elif ranking_criteria == 'composite':
                    # Composite score combining multiple factors
                    score = self._calculate_composite_score(metrics)
                else:
                    raise StrategyEvaluatorError(f"Unknown ranking criteria: {ranking_criteria}")
                
                rankings.append((strategy_type, score))
            
            # Sort by score descending
            rankings.sort(key=lambda x: x[1], reverse=True)
            
            # Determine evaluation period
            all_metrics = list(strategy_performances.values())
            period_start = min(m.evaluation_period_start for m in all_metrics)
            period_end = max(m.evaluation_period_end for m in all_metrics)
            
            ranking_result = StrategyRanking(
                rankings=rankings,
                ranking_criteria=ranking_criteria,
                evaluation_period=(period_start, period_end),
                total_strategies=len(rankings)
            )
            
            # Store in history
            self.ranking_history.append(ranking_result)
            
            return ranking_result
            
        except Exception as e:
            raise StrategyEvaluatorError(f"Failed to rank strategies: {e}")
    
    def _calculate_correct_predictions(self, 
                                     strategy_results: List[StrategyResult],
                                     actual_outcomes: List[float]) -> int:
        """Calculate number of correct predictions based on actual outcomes."""
        correct = 0
        
        for result, outcome in zip(strategy_results, actual_outcomes):
            # Consider prediction correct if:
            # - Recommended TRADE and outcome was positive
            # - Recommended AVOID and outcome was negative or zero
            if (result.recommendation == 'TRADE' and outcome > 0) or \
               (result.recommendation == 'AVOID' and outcome <= 0):
                correct += 1
        
        return correct
    
    def _calculate_classification_metrics(self, 
                                        strategy_results: List[StrategyResult],
                                        actual_outcomes: List[float]) -> Tuple[float, float, float]:
        """Calculate precision, recall, and F1 score."""
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        
        for result, outcome in zip(strategy_results, actual_outcomes):
            predicted_positive = result.recommendation == 'TRADE'
            actual_positive = outcome > 0
            
            if predicted_positive and actual_positive:
                true_positives += 1
            elif predicted_positive and not actual_positive:
                false_positives += 1
            elif not predicted_positive and actual_positive:
                false_negatives += 1
        
        # Calculate metrics
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        return precision, recall, f1_score
    
    def _calculate_sharpe_ratio(self, returns: List[float], risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio for returns."""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        
        if std_return == 0:
            return 0.0
        
        # Convert annual risk-free rate to per-recommendation rate
        risk_free_per_rec = risk_free_rate / 252  # Assuming daily recommendations
        
        return (mean_return - risk_free_per_rec) / std_return
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown from returns."""
        if not returns:
            return 0.0
        
        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative
        
        return float(np.max(drawdown))
    
    def _extract_metric_values(self, results: List[StrategyResult], metric_name: str) -> List[float]:
        """Extract specific metric values from strategy results."""
        if metric_name == 'accuracy':
            # Use confidence as proxy for accuracy
            return [r.confidence_score for r in results]
        elif metric_name == 'expected_return':
            return [r.expected_return for r in results]
        elif metric_name == 'confidence_score':
            return [r.confidence_score for r in results]
        elif metric_name == 'expected_risk':
            return [r.expected_risk for r in results]
        else:
            self.logger.warning(f"Unknown metric: {metric_name}")
            return []
    
    def _calculate_difference_confidence_interval(self, 
                                                values_a: List[float],
                                                values_b: List[float]) -> Tuple[float, float]:
        """Calculate confidence interval for the difference between two samples."""
        mean_a = np.mean(values_a)
        mean_b = np.mean(values_b)
        std_a = np.std(values_a, ddof=1)
        std_b = np.std(values_b, ddof=1)
        n_a = len(values_a)
        n_b = len(values_b)
        
        # Standard error of the difference
        se_diff = np.sqrt(std_a**2/n_a + std_b**2/n_b)
        
        # Degrees of freedom (Welch's formula)
        df = (std_a**2/n_a + std_b**2/n_b)**2 / ((std_a**2/n_a)**2/(n_a-1) + (std_b**2/n_b)**2/(n_b-1))
        
        # Critical value
        alpha = 1 - self.confidence_level
        t_critical = stats.t.ppf(1 - alpha/2, df)
        
        # Confidence interval
        difference = mean_a - mean_b
        margin_error = t_critical * se_diff
        
        return difference - margin_error, difference + margin_error
    
    def _calculate_composite_score(self, metrics: StrategyPerformanceMetrics) -> float:
        """Calculate composite score combining multiple performance factors."""
        # Weights for different components
        weights = {
            'accuracy': 0.25,
            'return': 0.25,
            'sharpe': 0.20,
            'confidence': 0.15,
            'win_rate': 0.10,
            'risk_penalty': 0.05
        }
        
        # Normalize metrics to 0-1 scale
        normalized_accuracy = max(0.0, min(1.0, metrics.accuracy))
        normalized_return = max(0.0, min(1.0, (metrics.average_expected_return + 1.0) / 2.0))  # Assuming returns in [-1, 1]
        normalized_sharpe = max(0.0, min(1.0, (metrics.sharpe_ratio + 2.0) / 4.0))  # Assuming Sharpe in [-2, 2]
        normalized_confidence = max(0.0, min(1.0, metrics.average_confidence))
        normalized_win_rate = max(0.0, min(1.0, metrics.win_rate))
        risk_penalty = max(0.0, min(1.0, 1.0 - metrics.average_expected_risk))
        
        # Calculate weighted composite score
        composite_score = (
            weights['accuracy'] * normalized_accuracy +
            weights['return'] * normalized_return +
            weights['sharpe'] * normalized_sharpe +
            weights['confidence'] * normalized_confidence +
            weights['win_rate'] * normalized_win_rate +
            weights['risk_penalty'] * risk_penalty
        )
        
        return composite_score
    
    def get_strategy_comparison_summary(self, lookback_days: int = 30) -> Dict[str, Any]:
        """
        Get summary of recent strategy comparisons.
        
        Args:
            lookback_days: Number of days to look back
            
        Returns:
            Dictionary with comparison summary
        """
        cutoff_date = datetime.now() - timedelta(days=lookback_days)
        recent_comparisons = [
            c for c in self.comparison_history
            if c.comparison_timestamp >= cutoff_date
        ]
        
        if not recent_comparisons:
            return {'message': 'No recent comparisons available'}
        
        # Aggregate results by strategy pair
        strategy_pairs = defaultdict(list)
        for comparison in recent_comparisons:
            pair_key = f"{comparison.strategy_a.value}_vs_{comparison.strategy_b.value}"
            strategy_pairs[pair_key].append(comparison)
        
        summary = {}
        for pair_key, comparisons in strategy_pairs.items():
            significant_differences = [c for c in comparisons if c.is_significant]
            
            summary[pair_key] = {
                'total_comparisons': len(comparisons),
                'significant_differences': len(significant_differences),
                'metrics_compared': list(set(c.metric_name for c in comparisons)),
                'average_p_value': np.mean([c.statistical_significance for c in comparisons]),
                'largest_difference': max(abs(c.difference) for c in comparisons) if comparisons else 0.0
            }
        
        summary['total_comparisons'] = len(recent_comparisons)
        summary['total_strategy_pairs'] = len(strategy_pairs)
        summary['evaluation_period'] = f"Last {lookback_days} days"
        
        return summary