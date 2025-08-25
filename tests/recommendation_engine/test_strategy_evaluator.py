"""
Unit tests for the strategy evaluator.

Tests strategy evaluation, comparison, and ranking functionality.

Requirements: 6.1, 6.4
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from trading_platform.services.recommendation.strategy_evaluator import (
    StrategyEvaluator, StrategyPerformanceMetrics, StrategyComparisonResult,
    StrategyRanking, StrategyEvaluatorError
)
from trading_platform.services.recommendation.recommendation_service import (
    StrategyType, StrategyResult, RecommendationContext
)


class TestStrategyEvaluator:
    """Test cases for StrategyEvaluator."""
    
    @pytest.fixture
    def evaluator(self):
        """Create strategy evaluator for testing."""
        return StrategyEvaluator(significance_threshold=0.05, confidence_level=0.95)
    
    @pytest.fixture
    def sample_strategy_results(self):
        """Create sample strategy results for testing."""
        results = []
        base_time = datetime(2024, 1, 1, 10, 0)
        
        for i in range(20):
            result = StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE' if i % 2 == 0 else 'AVOID',
                confidence_score=0.6 + (i % 5) * 0.1,  # 0.6 to 1.0
                expected_return=5.0 + i * 2.0,  # 5.0 to 43.0
                expected_risk=0.2 + (i % 3) * 0.1,  # 0.2 to 0.4
                reasoning=f"Strategy reasoning {i}",
                execution_time=0.1 + i * 0.01,
                timestamp=base_time + timedelta(hours=i)
            )
            results.append(result)
        
        return results
    
    @pytest.fixture
    def sample_contexts(self):
        """Create sample recommendation contexts."""
        contexts = []
        base_time = datetime(2024, 1, 1, 10, 0)
        
        for i in range(20):
            context = RecommendationContext(
                account_name="IPS_TM_10",
                symbol="NQ",
                current_time=base_time + timedelta(hours=i),
                hour_of_day=(10 + i) % 24,
                day_of_week=i % 7,
                historical_trades=[Mock()],  # Mock trades
                risk_tolerance=0.5
            )
            contexts.append(context)
        
        return contexts
    
    @pytest.fixture
    def sample_recommendations(self, sample_contexts, sample_strategy_results):
        """Create sample recommendations (context, result pairs)."""
        return list(zip(sample_contexts, sample_strategy_results))
    
    def test_initialization(self):
        """Test evaluator initialization."""
        evaluator = StrategyEvaluator(significance_threshold=0.01, confidence_level=0.99)
        
        assert evaluator.significance_threshold == 0.01
        assert evaluator.confidence_level == 0.99
        assert len(evaluator.strategy_history) == 0
        assert len(evaluator.comparison_history) == 0
        assert len(evaluator.ranking_history) == 0
    
    def test_evaluate_strategy_performance_basic(self, evaluator, sample_recommendations):
        """Test basic strategy performance evaluation."""
        metrics = evaluator.evaluate_strategy_performance(
            strategy_type=StrategyType.STATISTICAL,
            recommendations=sample_recommendations
        )
        
        assert isinstance(metrics, StrategyPerformanceMetrics)
        assert metrics.strategy_type == StrategyType.STATISTICAL
        assert metrics.total_recommendations == 20
        assert 0.0 <= metrics.accuracy <= 1.0
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1_score <= 1.0
        assert metrics.average_confidence > 0.0
        assert metrics.sample_trades >= 0
    
    def test_evaluate_strategy_performance_with_outcomes(self, evaluator, sample_recommendations):
        """Test strategy performance evaluation with actual outcomes."""
        # Create mock actual outcomes
        actual_outcomes = [10.0 if i % 2 == 0 else -5.0 for i in range(20)]
        
        metrics = evaluator.evaluate_strategy_performance(
            strategy_type=StrategyType.STATISTICAL,
            recommendations=sample_recommendations,
            actual_outcomes=actual_outcomes
        )
        
        assert isinstance(metrics, StrategyPerformanceMetrics)
        assert metrics.total_recommendations == 20
        
        # With actual outcomes, accuracy should be calculated properly
        # TRADE recommendations on positive outcomes and AVOID on negative should be correct
        expected_correct = sum(
            1 for i, (context, result) in enumerate(sample_recommendations)
            if (result.recommendation == 'TRADE' and actual_outcomes[i] > 0) or
               (result.recommendation == 'AVOID' and actual_outcomes[i] <= 0)
        )
        expected_accuracy = expected_correct / 20
        
        assert metrics.accuracy == expected_accuracy
        assert metrics.correct_predictions == expected_correct
    
    def test_evaluate_strategy_performance_empty_recommendations(self, evaluator):
        """Test evaluation with empty recommendations."""
        with pytest.raises(StrategyEvaluatorError, match="No recommendations provided"):
            evaluator.evaluate_strategy_performance(
                strategy_type=StrategyType.STATISTICAL,
                recommendations=[]
            )
    
    def test_evaluate_strategy_performance_wrong_strategy_type(self, evaluator, sample_recommendations):
        """Test evaluation with wrong strategy type."""
        # All sample results are STATISTICAL, but we're asking for ML
        with pytest.raises(StrategyEvaluatorError, match="No results found for strategy"):
            evaluator.evaluate_strategy_performance(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendations=sample_recommendations
            )
    
    def test_compare_strategies_basic(self, evaluator, sample_contexts):
        """Test basic strategy comparison."""
        # Create results for two different strategies
        results_a = []
        results_b = []
        
        for i, context in enumerate(sample_contexts):
            result_a = StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE' if i % 2 == 0 else 'AVOID',
                confidence_score=0.7 + (i % 3) * 0.1,
                expected_return=8.0 + i,
                expected_risk=0.3,
                reasoning="Statistical",
                execution_time=0.1
            )
            
            result_b = StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE' if i % 3 == 0 else 'AVOID',
                confidence_score=0.6 + (i % 4) * 0.1,
                expected_return=6.0 + i * 1.5,
                expected_risk=0.4,
                reasoning="ML",
                execution_time=0.2
            )
            
            results_a.append((context, result_a))
            results_b.append((context, result_b))
        
        comparisons = evaluator.compare_strategies(
            strategy_a=StrategyType.STATISTICAL,
            strategy_b=StrategyType.MACHINE_LEARNING,
            recommendations_a=results_a,
            recommendations_b=results_b
        )
        
        assert len(comparisons) > 0
        
        for comparison in comparisons:
            assert isinstance(comparison, StrategyComparisonResult)
            assert comparison.strategy_a == StrategyType.STATISTICAL
            assert comparison.strategy_b == StrategyType.MACHINE_LEARNING
            assert comparison.metric_name in ['accuracy', 'expected_return', 'confidence_score', 'expected_risk']
            assert isinstance(comparison.difference, float)
            assert isinstance(comparison.statistical_significance, float)
            assert isinstance(comparison.is_significant, bool)
    
    def test_compare_strategies_empty_recommendations(self, evaluator):
        """Test strategy comparison with empty recommendations."""
        with pytest.raises(StrategyEvaluatorError, match="Both strategies must have recommendations"):
            evaluator.compare_strategies(
                strategy_a=StrategyType.STATISTICAL,
                strategy_b=StrategyType.MACHINE_LEARNING,
                recommendations_a=[],
                recommendations_b=[]
            )
    
    def test_compare_strategies_custom_metrics(self, evaluator, sample_contexts):
        """Test strategy comparison with custom metrics."""
        # Create minimal results for testing
        results_a = [(sample_contexts[0], StrategyResult(
            strategy_type=StrategyType.STATISTICAL,
            recommendation='TRADE',
            confidence_score=0.8,
            expected_return=10.0,
            expected_risk=0.3,
            reasoning="Test",
            execution_time=0.1
        ))]
        
        results_b = [(sample_contexts[0], StrategyResult(
            strategy_type=StrategyType.MACHINE_LEARNING,
            recommendation='AVOID',
            confidence_score=0.6,
            expected_return=5.0,
            expected_risk=0.5,
            reasoning="Test",
            execution_time=0.2
        ))]
        
        comparisons = evaluator.compare_strategies(
            strategy_a=StrategyType.STATISTICAL,
            strategy_b=StrategyType.MACHINE_LEARNING,
            recommendations_a=results_a,
            recommendations_b=results_b,
            metrics_to_compare=['confidence_score', 'expected_return']
        )
        
        assert len(comparisons) == 2
        metric_names = [c.metric_name for c in comparisons]
        assert 'confidence_score' in metric_names
        assert 'expected_return' in metric_names
    
    def test_rank_strategies_accuracy(self, evaluator):
        """Test strategy ranking by accuracy."""
        # Create mock performance metrics
        performances = {
            StrategyType.STATISTICAL: StrategyPerformanceMetrics(
                strategy_type=StrategyType.STATISTICAL,
                total_recommendations=100,
                correct_predictions=80,
                accuracy=0.8,
                precision=0.75,
                recall=0.85,
                f1_score=0.8,
                average_confidence=0.7,
                average_expected_return=10.0,
                average_expected_risk=0.3,
                sharpe_ratio=1.2,
                max_drawdown=0.15,
                win_rate=0.6,
                profit_factor=1.5,
                evaluation_period_start=datetime(2024, 1, 1),
                evaluation_period_end=datetime(2024, 1, 31),
                sample_trades=1000
            ),
            StrategyType.MACHINE_LEARNING: StrategyPerformanceMetrics(
                strategy_type=StrategyType.MACHINE_LEARNING,
                total_recommendations=100,
                correct_predictions=75,
                accuracy=0.75,
                precision=0.8,
                recall=0.7,
                f1_score=0.75,
                average_confidence=0.8,
                average_expected_return=12.0,
                average_expected_risk=0.4,
                sharpe_ratio=1.0,
                max_drawdown=0.2,
                win_rate=0.65,
                profit_factor=1.3,
                evaluation_period_start=datetime(2024, 1, 1),
                evaluation_period_end=datetime(2024, 1, 31),
                sample_trades=1000
            )
        }
        
        ranking = evaluator.rank_strategies(performances, ranking_criteria='accuracy')
        
        assert isinstance(ranking, StrategyRanking)
        assert len(ranking.rankings) == 2
        assert ranking.ranking_criteria == 'accuracy'
        
        # Statistical should be first (higher accuracy)
        assert ranking.rankings[0][0] == StrategyType.STATISTICAL
        assert ranking.rankings[0][1] == 0.8
        assert ranking.rankings[1][0] == StrategyType.MACHINE_LEARNING
        assert ranking.rankings[1][1] == 0.75
    
    def test_rank_strategies_composite(self, evaluator):
        """Test strategy ranking by composite score."""
        # Create mock performance metrics
        performances = {
            StrategyType.STATISTICAL: StrategyPerformanceMetrics(
                strategy_type=StrategyType.STATISTICAL,
                total_recommendations=100,
                correct_predictions=70,
                accuracy=0.7,
                precision=0.75,
                recall=0.65,
                f1_score=0.7,
                average_confidence=0.8,
                average_expected_return=0.1,  # Normalized to [-1, 1] range
                average_expected_risk=0.3,
                sharpe_ratio=1.0,  # Normalized to [-2, 2] range
                max_drawdown=0.15,
                win_rate=0.6,
                profit_factor=1.5,
                evaluation_period_start=datetime(2024, 1, 1),
                evaluation_period_end=datetime(2024, 1, 31),
                sample_trades=1000
            )
        }
        
        ranking = evaluator.rank_strategies(performances, ranking_criteria='composite')
        
        assert isinstance(ranking, StrategyRanking)
        assert len(ranking.rankings) == 1
        assert ranking.ranking_criteria == 'composite'
        assert 0.0 <= ranking.rankings[0][1] <= 1.0  # Composite score should be normalized
    
    def test_rank_strategies_empty_performances(self, evaluator):
        """Test ranking with empty performances."""
        with pytest.raises(StrategyEvaluatorError, match="No strategy performances provided"):
            evaluator.rank_strategies({})
    
    def test_rank_strategies_invalid_criteria(self, evaluator):
        """Test ranking with invalid criteria."""
        performances = {
            StrategyType.STATISTICAL: Mock(accuracy=0.8)
        }
        
        with pytest.raises(StrategyEvaluatorError, match="Unknown ranking criteria"):
            evaluator.rank_strategies(performances, ranking_criteria='invalid')
    
    def test_calculate_correct_predictions(self, evaluator):
        """Test correct prediction calculation."""
        strategy_results = [
            StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=10.0,
                expected_risk=0.3,
                reasoning="Test",
                execution_time=0.1
            ),
            StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='AVOID',
                confidence_score=0.7,
                expected_return=5.0,
                expected_risk=0.4,
                reasoning="Test",
                execution_time=0.1
            ),
            StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.6,
                expected_return=8.0,
                expected_risk=0.5,
                reasoning="Test",
                execution_time=0.1
            )
        ]
        
        actual_outcomes = [15.0, -5.0, -2.0]  # Positive, Negative, Negative
        
        correct = evaluator._calculate_correct_predictions(strategy_results, actual_outcomes)
        
        # First: TRADE with positive outcome = correct
        # Second: AVOID with negative outcome = correct
        # Third: TRADE with negative outcome = incorrect
        assert correct == 2
    
    def test_calculate_classification_metrics(self, evaluator):
        """Test classification metrics calculation."""
        strategy_results = [
            # True Positive: TRADE with positive outcome
            StrategyResult(StrategyType.STATISTICAL, 'TRADE', 0.8, 10.0, 0.3, "Test", 0.1),
            # True Negative: AVOID with negative outcome
            StrategyResult(StrategyType.STATISTICAL, 'AVOID', 0.7, 5.0, 0.4, "Test", 0.1),
            # False Positive: TRADE with negative outcome
            StrategyResult(StrategyType.STATISTICAL, 'TRADE', 0.6, 8.0, 0.5, "Test", 0.1),
            # False Negative: AVOID with positive outcome
            StrategyResult(StrategyType.STATISTICAL, 'AVOID', 0.5, 3.0, 0.6, "Test", 0.1)
        ]
        
        actual_outcomes = [15.0, -5.0, -2.0, 8.0]
        
        precision, recall, f1_score = evaluator._calculate_classification_metrics(
            strategy_results, actual_outcomes
        )
        
        # TP=1, FP=1, FN=1, TN=1
        # Precision = TP/(TP+FP) = 1/2 = 0.5
        # Recall = TP/(TP+FN) = 1/2 = 0.5
        # F1 = 2*(P*R)/(P+R) = 2*(0.5*0.5)/(0.5+0.5) = 0.5
        
        assert precision == 0.5
        assert recall == 0.5
        assert f1_score == 0.5
    
    def test_calculate_sharpe_ratio(self, evaluator):
        """Test Sharpe ratio calculation."""
        returns = [0.1, 0.05, -0.02, 0.08, 0.03]
        
        sharpe = evaluator._calculate_sharpe_ratio(returns)
        
        assert isinstance(sharpe, float)
        assert sharpe != 0.0  # Should be non-zero for non-constant returns
        
        # Test edge cases
        assert evaluator._calculate_sharpe_ratio([]) == 0.0
        assert evaluator._calculate_sharpe_ratio([0.1]) == 0.0
        assert evaluator._calculate_sharpe_ratio([0.1, 0.1, 0.1]) == 0.0  # Zero std
    
    def test_calculate_max_drawdown(self, evaluator):
        """Test maximum drawdown calculation."""
        returns = [0.1, -0.05, 0.08, -0.12, 0.06]
        
        max_dd = evaluator._calculate_max_drawdown(returns)
        
        assert isinstance(max_dd, float)
        assert max_dd >= 0.0  # Drawdown should be positive
        
        # Test edge cases
        assert evaluator._calculate_max_drawdown([]) == 0.0
        assert evaluator._calculate_max_drawdown([0.1, 0.2, 0.3]) >= 0.0  # Only positive returns
    
    def test_extract_metric_values(self, evaluator):
        """Test metric value extraction."""
        results = [
            StrategyResult(StrategyType.STATISTICAL, 'TRADE', 0.8, 10.0, 0.3, "Test", 0.1),
            StrategyResult(StrategyType.STATISTICAL, 'AVOID', 0.7, 5.0, 0.4, "Test", 0.1)
        ]
        
        # Test different metrics
        confidence_values = evaluator._extract_metric_values(results, 'confidence_score')
        assert confidence_values == [0.8, 0.7]
        
        return_values = evaluator._extract_metric_values(results, 'expected_return')
        assert return_values == [10.0, 5.0]
        
        risk_values = evaluator._extract_metric_values(results, 'expected_risk')
        assert risk_values == [0.3, 0.4]
        
        # Test unknown metric
        unknown_values = evaluator._extract_metric_values(results, 'unknown_metric')
        assert unknown_values == []
    
    def test_calculate_composite_score(self, evaluator):
        """Test composite score calculation."""
        metrics = StrategyPerformanceMetrics(
            strategy_type=StrategyType.STATISTICAL,
            total_recommendations=100,
            correct_predictions=80,
            accuracy=0.8,
            precision=0.75,
            recall=0.85,
            f1_score=0.8,
            average_confidence=0.7,
            average_expected_return=0.1,  # Normalized
            average_expected_risk=0.3,
            sharpe_ratio=1.0,  # Normalized
            max_drawdown=0.15,
            win_rate=0.6,
            profit_factor=1.5,
            evaluation_period_start=datetime(2024, 1, 1),
            evaluation_period_end=datetime(2024, 1, 31),
            sample_trades=1000
        )
        
        score = evaluator._calculate_composite_score(metrics)
        
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0  # Should be normalized
    
    def test_get_strategy_comparison_summary(self, evaluator):
        """Test strategy comparison summary generation."""
        # Add some mock comparisons to history
        comparison = StrategyComparisonResult(
            strategy_a=StrategyType.STATISTICAL,
            strategy_b=StrategyType.MACHINE_LEARNING,
            metric_name='accuracy',
            strategy_a_value=0.8,
            strategy_b_value=0.75,
            difference=0.05,
            percentage_difference=6.67,
            statistical_significance=0.03,
            is_significant=True,
            confidence_interval_lower=0.01,
            confidence_interval_upper=0.09,
            sample_size=100,
            test_statistic=2.1,
            comparison_timestamp=datetime.now()
        )
        
        evaluator.comparison_history.append(comparison)
        
        summary = evaluator.get_strategy_comparison_summary(lookback_days=30)
        
        assert isinstance(summary, dict)
        assert 'total_comparisons' in summary
        assert 'total_strategy_pairs' in summary
        assert summary['total_comparisons'] == 1
        
        # Test with no comparisons
        evaluator.comparison_history.clear()
        summary = evaluator.get_strategy_comparison_summary(lookback_days=30)
        assert 'message' in summary
        assert 'No recent comparisons available' in summary['message']


if __name__ == '__main__':
    pytest.main([__file__])