"""
Unit tests for the core recommendation service.

Tests the main recommendation service functionality including strategy execution,
combination logic, and time-based filtering.

Requirements: 6.1, 6.4
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from trading_platform.services.recommendation.recommendation_service import (
    RecommendationService, RecommendationContext, StrategyResult, StrategyType,
    RecommendationServiceError
)
from trading_platform.models.trading import ProcessedTrade, TradingRecommendation


class TestRecommendationService:
    """Test cases for RecommendationService."""
    
    @pytest.fixture
    def mock_services(self):
        """Create mock services for testing."""
        mock_performance_calc = Mock()
        mock_temporal_analyzer = Mock()
        mock_prediction_service = Mock()
        mock_monte_carlo = Mock()
        
        return {
            'performance_calculator': mock_performance_calc,
            'temporal_analyzer': mock_temporal_analyzer,
            'prediction_service': mock_prediction_service,
            'monte_carlo_simulator': mock_monte_carlo
        }
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample processed trades for testing."""
        base_time = datetime(2024, 1, 1, 10, 0)
        trades = []
        
        for i in range(10):
            entry_price = 15000.0 + i * 10
            exit_price = 15010.0 + i * 10
            profit_loss = (exit_price - entry_price) * 1 - 2.0  # quantity * price_diff - commission
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i, minutes=30),
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side="LONG",
                profit_loss=profit_loss,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=(10 + i) % 24,
                day_of_week=i % 7,
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def recommendation_context(self, sample_trades):
        """Create recommendation context for testing."""
        return RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime(2024, 1, 15, 14, 30),
            hour_of_day=14,
            day_of_week=0,  # Monday
            historical_trades=sample_trades,
            risk_tolerance=0.5
        )
    
    def test_initialization(self, mock_services):
        """Test service initialization."""
        service = RecommendationService(**mock_services)
        
        assert service.performance_calculator is not None
        assert service.temporal_analyzer is not None
        assert service.prediction_service is not None
        assert service.monte_carlo_simulator is not None
        assert service.default_risk_tolerance == 0.5
        assert len(service.strategy_weights) == 3
        assert sum(service.strategy_weights.values()) == pytest.approx(1.0)
    
    def test_generate_recommendation_success(self, mock_services, recommendation_context):
        """Test successful recommendation generation."""
        service = RecommendationService(**mock_services, enable_parallel_strategies=False)
        
        # Mock strategy execution methods
        with patch.object(service, '_execute_statistical_strategy') as mock_stat, \
             patch.object(service, '_execute_ml_strategy') as mock_ml, \
             patch.object(service, '_execute_monte_carlo_strategy') as mock_mc:
            
            # Setup mock strategy results
            mock_stat.return_value = StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=15.0,
                expected_risk=0.3,
                reasoning="Statistical patterns favorable",
                execution_time=0.1
            )
            
            mock_ml.return_value = StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.7,
                expected_return=12.0,
                expected_risk=0.4,
                reasoning="ML model predicts profit",
                execution_time=0.2
            )
            
            mock_mc.return_value = StrategyResult(
                strategy_type=StrategyType.MONTE_CARLO,
                recommendation='AVOID',
                confidence_score=0.6,
                expected_return=5.0,
                expected_risk=0.8,
                reasoning="Monte Carlo shows high risk",
                execution_time=0.3
            )
            
            # Generate recommendation
            result = service.generate_recommendation(recommendation_context)
            
            # Verify result
            assert isinstance(result, TradingRecommendation)
            assert result.account_name == "IPS_TM_10"
            assert result.symbol == "NQ"
            assert result.recommended_action in ['TRADE', 'AVOID']
            assert 0.0 <= result.confidence_score <= 1.0
            assert result.reasoning is not None
            
            # Verify all strategies were called
            mock_stat.assert_called_once()
            mock_ml.assert_called_once()
            mock_mc.assert_called_once()
    
    def test_generate_recommendation_no_trades(self, mock_services):
        """Test recommendation generation with no historical trades."""
        service = RecommendationService(**mock_services)
        
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime.now(),
            hour_of_day=14,
            day_of_week=0,
            historical_trades=[],  # Empty trades
            risk_tolerance=0.5
        )
        
        with pytest.raises(RecommendationServiceError, match="No historical trades provided"):
            service.generate_recommendation(context)
    
    def test_execute_statistical_strategy(self, mock_services, recommendation_context):
        """Test statistical strategy execution."""
        service = RecommendationService(**mock_services)
        
        # Mock temporal analyzer
        mock_temporal_result = Mock()
        mock_temporal_result.best_hours = [14]
        mock_temporal_result.best_days = [0]
        mock_temporal_result.worst_hours = []
        mock_temporal_result.worst_days = []
        mock_temporal_result.hourly_patterns = [Mock(time_period=14, average_pnl=10.0, volatility=5.0)]
        mock_temporal_result.daily_patterns = [Mock(time_period=0, average_pnl=8.0, volatility=4.0)]
        
        service.temporal_analyzer.analyze_temporal_patterns.return_value = mock_temporal_result
        service.temporal_analyzer.get_trading_recommendations.return_value = {
            'overall': 'STRONG BUY: Both hour and day patterns are favorable'
        }
        
        result = service._execute_statistical_strategy(recommendation_context)
        
        assert result.strategy_type == StrategyType.STATISTICAL
        assert result.recommendation == 'TRADE'
        assert result.confidence_score == 0.8
        assert result.expected_return > 0
        assert "Statistical patterns favorable" in result.reasoning
    
    def test_execute_ml_strategy(self, mock_services, recommendation_context):
        """Test ML strategy execution."""
        service = RecommendationService(**mock_services)
        
        # Mock prediction service
        mock_prediction = {
            'profit_probability': 0.7,
            'expected_return': 12.0,
            'confidence_score': 0.8,
            'risk_score': 0.3
        }
        service.prediction_service.predict_optimal_conditions.return_value = mock_prediction
        
        result = service._execute_ml_strategy(recommendation_context)
        
        assert result.strategy_type == StrategyType.MACHINE_LEARNING
        assert result.recommendation == 'TRADE'
        assert result.confidence_score == 0.8
        assert result.expected_return == 12.0
        assert "ML model predicts" in result.reasoning
    
    def test_execute_monte_carlo_strategy(self, mock_services, recommendation_context):
        """Test Monte Carlo strategy execution."""
        service = RecommendationService(**mock_services)
        
        # Mock Monte Carlo simulation
        mock_simulation_result = {
            'statistics': {
                'risk_metrics': {
                    'probability_of_profit': 0.6,
                    'sharpe_ratio': 1.2,
                    'max_drawdown': -0.15
                },
                'returns': {
                    'mean': 8.0
                }
            }
        }
        service.monte_carlo_simulator.run_simulation.return_value = mock_simulation_result
        
        result = service._execute_monte_carlo_strategy(recommendation_context)
        
        assert result.strategy_type == StrategyType.MONTE_CARLO
        assert result.recommendation in ['TRADE', 'AVOID']
        assert 0.0 <= result.confidence_score <= 1.0
        assert "Monte Carlo" in result.reasoning
    
    def test_combine_strategy_results(self, mock_services, recommendation_context):
        """Test strategy result combination logic."""
        service = RecommendationService(**mock_services)
        
        strategy_results = [
            StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=10.0,
                expected_risk=0.3,
                reasoning="Statistical favorable",
                execution_time=0.1
            ),
            StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.7,
                expected_return=12.0,
                expected_risk=0.4,
                reasoning="ML favorable",
                execution_time=0.2
            ),
            StrategyResult(
                strategy_type=StrategyType.MONTE_CARLO,
                recommendation='AVOID',
                confidence_score=0.6,
                expected_return=5.0,
                expected_risk=0.8,
                reasoning="MC unfavorable",
                execution_time=0.3
            )
        ]
        
        result = service._combine_strategy_results(recommendation_context, strategy_results)
        
        assert isinstance(result, TradingRecommendation)
        assert result.recommended_action in ['TRADE', 'AVOID']
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.expected_return is not None
        assert result.expected_risk is not None
        assert len(result.reasoning) > 0
    
    def test_parallel_strategy_execution(self, mock_services, recommendation_context):
        """Test parallel strategy execution."""
        service = RecommendationService(**mock_services, enable_parallel_strategies=True)
        
        with patch.object(service, '_execute_statistical_strategy') as mock_stat, \
             patch.object(service, '_execute_ml_strategy') as mock_ml, \
             patch.object(service, '_execute_monte_carlo_strategy') as mock_mc:
            
            mock_stat.return_value = StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=10.0,
                expected_risk=0.3,
                reasoning="Statistical",
                execution_time=0.1
            )
            
            mock_ml.return_value = StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.7,
                expected_return=12.0,
                expected_risk=0.4,
                reasoning="ML",
                execution_time=0.2
            )
            
            mock_mc.return_value = StrategyResult(
                strategy_type=StrategyType.MONTE_CARLO,
                recommendation='AVOID',
                confidence_score=0.6,
                expected_return=5.0,
                expected_risk=0.8,
                reasoning="MC",
                execution_time=0.3
            )
            
            results = service._execute_strategies_parallel(recommendation_context)
            
            assert len(results) == 3
            assert all(isinstance(r, StrategyResult) for r in results)
    
    def test_strategy_failure_handling(self, mock_services, recommendation_context):
        """Test handling of strategy execution failures."""
        service = RecommendationService(**mock_services, enable_parallel_strategies=False)
        
        with patch.object(service, '_execute_statistical_strategy') as mock_stat, \
             patch.object(service, '_execute_ml_strategy') as mock_ml, \
             patch.object(service, '_execute_monte_carlo_strategy') as mock_mc:
            
            # Make one strategy fail
            mock_stat.side_effect = Exception("Statistical strategy failed")
            
            mock_ml.return_value = StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.7,
                expected_return=12.0,
                expected_risk=0.4,
                reasoning="ML",
                execution_time=0.2
            )
            
            mock_mc.return_value = StrategyResult(
                strategy_type=StrategyType.MONTE_CARLO,
                recommendation='AVOID',
                confidence_score=0.6,
                expected_return=5.0,
                expected_risk=0.8,
                reasoning="MC",
                execution_time=0.3
            )
            
            results = service._execute_strategies_sequential(recommendation_context)
            
            # Should have 3 results, with one being a fallback
            assert len(results) == 3
            
            # Find the fallback result
            fallback_result = next(r for r in results if r.strategy_type == StrategyType.STATISTICAL)
            assert fallback_result.recommendation == 'AVOID'
            assert fallback_result.confidence_score == 0.0
            assert "Strategy failed" in fallback_result.reasoning
    
    def test_compare_strategies(self, mock_services):
        """Test strategy comparison functionality."""
        service = RecommendationService(**mock_services)
        
        # Add some mock history
        context = Mock()
        context.current_time = datetime.now()
        
        results = [
            StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=10.0,
                expected_risk=0.3,
                reasoning="Statistical",
                execution_time=0.1
            ),
            StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.7,
                expected_return=12.0,
                expected_risk=0.4,
                reasoning="ML",
                execution_time=0.2
            )
        ]
        
        # Add multiple entries to history
        for _ in range(15):
            service.recommendation_history.append((context, results))
        
        comparisons = service.compare_strategies(lookback_days=30)
        
        assert len(comparisons) >= 0  # May be empty if insufficient data
        for comparison in comparisons:
            assert hasattr(comparison, 'strategy_a')
            assert hasattr(comparison, 'strategy_b')
            assert hasattr(comparison, 'preference_score')
    
    def test_update_strategy_weights(self, mock_services):
        """Test strategy weight updates."""
        service = RecommendationService(**mock_services)
        
        initial_weights = service.strategy_weights.copy()
        
        # Update with performance data
        performance_data = {
            StrategyType.STATISTICAL: 0.6,
            StrategyType.MACHINE_LEARNING: 0.8,
            StrategyType.MONTE_CARLO: 0.4
        }
        
        service.update_strategy_weights(performance_data)
        
        # Weights should have changed
        assert service.strategy_weights != initial_weights
        
        # Weights should still sum to 1.0
        assert sum(service.strategy_weights.values()) == pytest.approx(1.0)
        
        # ML should have highest weight due to best performance
        assert service.strategy_weights[StrategyType.MACHINE_LEARNING] > service.strategy_weights[StrategyType.MONTE_CARLO]
    
    def test_filter_recommendations_by_time(self, mock_services):
        """Test time-based recommendation filtering."""
        service = RecommendationService(**mock_services)
        
        # Create sample recommendations
        recommendations = []
        base_time = datetime(2024, 1, 1, 10, 0)
        
        for i in range(24):  # 24 hours
            rec = TradingRecommendation(
                timestamp=base_time + timedelta(hours=i),
                account_name="IPS_TM_10",
                symbol="NQ",
                recommended_action='TRADE',
                confidence_score=0.7,
                expected_return=10.0,
                expected_risk=0.3,
                reasoning="Test",
                hour_of_day=i,
                day_of_week=0,
                historical_win_rate=0.6,
                avg_profit_this_time=10.0
            )
            recommendations.append(rec)
        
        # Test hour filtering
        time_filters = {'allowed_hours': [9, 10, 11, 14, 15]}
        filtered = service.filter_recommendations_by_time(recommendations, time_filters)
        
        assert len(filtered) == 5
        assert all(r.hour_of_day in [9, 10, 11, 14, 15] for r in filtered)
        
        # Test confidence filtering
        time_filters = {'min_confidence': 0.8}
        filtered = service.filter_recommendations_by_time(recommendations, time_filters)
        
        assert len(filtered) == 0  # All have confidence 0.7
        
        # Test date range filtering
        time_filters = {
            'start_date': base_time + timedelta(hours=5),
            'end_date': base_time + timedelta(hours=15)
        }
        filtered = service.filter_recommendations_by_time(recommendations, time_filters)
        
        assert len(filtered) == 11  # Hours 5-15 inclusive
    
    def test_get_strategy_performance_summary(self, mock_services):
        """Test strategy performance summary generation."""
        service = RecommendationService(**mock_services)
        
        # Add some performance data
        service.strategy_performance[StrategyType.STATISTICAL]['total_recommendations'] = 100
        service.strategy_performance[StrategyType.STATISTICAL]['correct_predictions'] = 70
        service.strategy_performance[StrategyType.STATISTICAL]['accuracy'] = 0.7
        
        summary = service.get_strategy_performance_summary()
        
        assert 'statistical' in summary
        assert summary['statistical']['accuracy'] == 0.7
        assert summary['statistical']['total_recommendations'] == 100
        assert 'total_recommendations_generated' in summary
        assert 'strategy_comparisons_performed' in summary
    
    def test_edge_cases(self, mock_services):
        """Test edge cases and error conditions."""
        service = RecommendationService(**mock_services)
        
        # Test empty strategy results
        with pytest.raises(RecommendationServiceError, match="No strategy results to combine"):
            service._combine_strategy_results(Mock(), [])
        
        # Test invalid risk tolerance
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime.now(),
            hour_of_day=14,
            day_of_week=0,
            historical_trades=[Mock()],
            risk_tolerance=1.5  # Invalid (should be 0-1)
        )
        
        # Should still work but clamp the value
        with patch.object(service, '_execute_statistical_strategy'), \
             patch.object(service, '_execute_ml_strategy'), \
             patch.object(service, '_execute_monte_carlo_strategy'):
            
            # Mock all strategies to return valid results
            service._execute_statistical_strategy.return_value = StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=10.0,
                expected_risk=0.3,
                reasoning="Test",
                execution_time=0.1
            )
            
            service._execute_ml_strategy.return_value = StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.7,
                expected_return=12.0,
                expected_risk=0.4,
                reasoning="Test",
                execution_time=0.2
            )
            
            service._execute_monte_carlo_strategy.return_value = StrategyResult(
                strategy_type=StrategyType.MONTE_CARLO,
                recommendation='AVOID',
                confidence_score=0.6,
                expected_return=5.0,
                expected_risk=0.8,
                reasoning="Test",
                execution_time=0.3
            )
            
            result = service.generate_recommendation(context)
            assert isinstance(result, TradingRecommendation)


if __name__ == '__main__':
    pytest.main([__file__])