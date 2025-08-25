"""
Integration tests for the recommendation engine.

Tests the integration between recommendation service, strategy evaluator,
and all analysis components.

Requirements: 6.1, 6.4
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from trading_platform.services.recommendation.recommendation_service import (
    RecommendationService, RecommendationContext, StrategyType
)
from trading_platform.services.recommendation.strategy_evaluator import StrategyEvaluator
from trading_platform.services.performance_metrics_calculator import PerformanceMetricsCalculator
from trading_platform.services.temporal_analysis_service import TemporalAnalysisService
from trading_platform.services.machine_learning.prediction_service import PredictionService
from trading_platform.services.monte_carlo.monte_carlo_simulator import MonteCarloSimulator
from trading_platform.models.trading import ProcessedTrade, TradingRecommendation


class TestRecommendationIntegration:
    """Integration test cases for recommendation engine."""
    
    @pytest.fixture
    def sample_trades(self):
        """Create comprehensive sample trades for integration testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0)
        
        # Create trades with varied patterns
        for i in range(100):
            # Create some temporal patterns
            hour = (9 + i) % 24
            day = i % 7
            
            # Make certain hours/days more profitable
            base_profit = 10.0
            if hour in [10, 11, 14, 15]:  # Good hours
                base_profit += 5.0
            if day in [1, 2, 3]:  # Good days (Tue, Wed, Thu)
                base_profit += 3.0
            
            # Add some randomness
            profit_variation = np.random.normal(0, 5)
            final_profit = base_profit + profit_variation
            
            entry_price = 15000.0 + i * 10
            exit_price = 15000.0 + i * 10 + final_profit
            side = "LONG" if i % 2 == 0 else "SHORT"
            
            # Calculate correct P&L based on side
            if side == "LONG":
                calculated_pnl = (exit_price - entry_price) * 1 - 2.0
            else:  # SHORT
                calculated_pnl = (entry_price - exit_price) * 1 - 2.0
            
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name="IPS_TM_10" if i % 2 == 0 else "IPS_TM_13",
                symbol="NQ" if i % 3 == 0 else "FDAX",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i, minutes=30),
                entry_price=entry_price,
                exit_price=exit_price,
                quantity=1,
                side=side,
                profit_loss=calculated_pnl,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=hour,
                day_of_week=day,
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def mock_prediction_service(self):
        """Create mock prediction service with realistic responses."""
        mock_service = Mock(spec=PredictionService)
        
        def mock_predict_optimal_conditions(conditions):
            # Simulate ML predictions based on time patterns
            hour = conditions.get('hour_of_day', 12)
            day = conditions.get('day_of_week', 0)
            
            # Simulate learned patterns
            if hour in [10, 11, 14, 15] and day in [1, 2, 3]:
                return {
                    'profit_probability': 0.75,
                    'expected_return': 15.0,
                    'confidence_score': 0.8,
                    'risk_score': 0.3
                }
            elif hour in [10, 11, 14, 15] or day in [1, 2, 3]:
                return {
                    'profit_probability': 0.65,
                    'expected_return': 10.0,
                    'confidence_score': 0.7,
                    'risk_score': 0.4
                }
            else:
                return {
                    'profit_probability': 0.45,
                    'expected_return': 5.0,
                    'confidence_score': 0.5,
                    'risk_score': 0.6
                }
        
        mock_service.predict_optimal_conditions.side_effect = mock_predict_optimal_conditions
        return mock_service
    
    @pytest.fixture
    def mock_monte_carlo_simulator(self):
        """Create mock Monte Carlo simulator with realistic responses."""
        mock_simulator = Mock(spec=MonteCarloSimulator)
        
        def mock_run_simulation(trades, num_simulations=1000, time_horizon=30):
            # Simulate Monte Carlo results based on trade history
            returns = [t.profit_loss for t in trades]
            mean_return = np.mean(returns)
            std_return = np.std(returns)
            
            # Simulate risk metrics
            prob_profit = 0.6 if mean_return > 0 else 0.4
            sharpe = mean_return / std_return if std_return > 0 else 0.0
            max_dd = abs(min(returns)) / 100.0 if returns else 0.1
            
            return {
                'statistics': {
                    'risk_metrics': {
                        'probability_of_profit': prob_profit,
                        'sharpe_ratio': sharpe,
                        'max_drawdown': max_dd
                    },
                    'returns': {
                        'mean': mean_return
                    }
                }
            }
        
        mock_simulator.run_simulation.side_effect = mock_run_simulation
        return mock_simulator
    
    def test_full_recommendation_pipeline(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test the complete recommendation pipeline integration."""
        # Create real services for statistical analysis
        performance_calculator = PerformanceMetricsCalculator()
        temporal_analyzer = TemporalAnalysisService()
        
        # Create recommendation service with mix of real and mock services
        recommendation_service = RecommendationService(
            performance_calculator=performance_calculator,
            temporal_analyzer=temporal_analyzer,
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator,
            enable_parallel_strategies=False  # Easier to debug
        )
        
        # Create recommendation context for a favorable time
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime(2024, 1, 15, 14, 30),  # Good hour
            hour_of_day=14,
            day_of_week=1,  # Tuesday (good day)
            historical_trades=sample_trades,
            risk_tolerance=0.5
        )
        
        # Generate recommendation
        recommendation = recommendation_service.generate_recommendation(context)
        
        # Verify recommendation structure
        assert isinstance(recommendation, TradingRecommendation)
        assert recommendation.account_name == "IPS_TM_10"
        assert recommendation.symbol == "NQ"
        assert recommendation.recommended_action in ['TRADE', 'AVOID']
        assert 0.0 <= recommendation.confidence_score <= 1.0
        assert recommendation.reasoning is not None
        assert len(recommendation.reasoning) > 0
        
        # For favorable time, should likely recommend TRADE
        # (though not guaranteed due to ensemble nature)
        print(f"Recommendation: {recommendation.recommended_action}")
        print(f"Confidence: {recommendation.confidence_score}")
        print(f"Reasoning: {recommendation.reasoning}")
    
    def test_unfavorable_time_recommendation(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test recommendation for unfavorable time periods."""
        # Create services
        performance_calculator = PerformanceMetricsCalculator()
        temporal_analyzer = TemporalAnalysisService()
        
        recommendation_service = RecommendationService(
            performance_calculator=performance_calculator,
            temporal_analyzer=temporal_analyzer,
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator,
            enable_parallel_strategies=False
        )
        
        # Create context for unfavorable time
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime(2024, 1, 15, 2, 30),  # Bad hour
            hour_of_day=2,
            day_of_week=5,  # Saturday (bad day)
            historical_trades=sample_trades,
            risk_tolerance=0.3  # Conservative
        )
        
        recommendation = recommendation_service.generate_recommendation(context)
        
        assert isinstance(recommendation, TradingRecommendation)
        # For unfavorable time, should likely recommend AVOID
        print(f"Unfavorable time recommendation: {recommendation.recommended_action}")
        print(f"Confidence: {recommendation.confidence_score}")
    
    def test_strategy_comparison_integration(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test strategy comparison functionality."""
        # Create services
        recommendation_service = RecommendationService(
            performance_calculator=PerformanceMetricsCalculator(),
            temporal_analyzer=TemporalAnalysisService(),
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator,
            enable_parallel_strategies=False
        )
        
        evaluator = StrategyEvaluator()
        
        # Generate multiple recommendations to build history
        contexts = []
        for i in range(20):
            context = RecommendationContext(
                account_name="IPS_TM_10",
                symbol="NQ",
                current_time=datetime(2024, 1, 1) + timedelta(hours=i),
                hour_of_day=(9 + i) % 24,
                day_of_week=i % 7,
                historical_trades=sample_trades,
                risk_tolerance=0.5
            )
            contexts.append(context)
            
            # Generate recommendation (this builds internal history)
            recommendation_service.generate_recommendation(context)
        
        # Compare strategies
        comparisons = recommendation_service.compare_strategies(lookback_days=30)
        
        # Should have some comparisons if there's sufficient history
        print(f"Generated {len(comparisons)} strategy comparisons")
        
        for comparison in comparisons[:3]:  # Show first 3
            print(f"Strategy {comparison.strategy_a.value} vs {comparison.strategy_b.value}")
            print(f"  Preference score: {comparison.preference_score}")
    
    def test_strategy_weight_adaptation(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test strategy weight adaptation based on performance."""
        recommendation_service = RecommendationService(
            performance_calculator=PerformanceMetricsCalculator(),
            temporal_analyzer=TemporalAnalysisService(),
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator
        )
        
        # Record initial weights
        initial_weights = recommendation_service.strategy_weights.copy()
        
        # Simulate performance data showing ML is best
        performance_data = {
            StrategyType.STATISTICAL: 0.6,
            StrategyType.MACHINE_LEARNING: 0.9,  # Best performance
            StrategyType.MONTE_CARLO: 0.4
        }
        
        # Update weights
        recommendation_service.update_strategy_weights(performance_data)
        
        # Verify weights changed
        assert recommendation_service.strategy_weights != initial_weights
        
        # ML should have higher weight now
        assert (recommendation_service.strategy_weights[StrategyType.MACHINE_LEARNING] > 
                recommendation_service.strategy_weights[StrategyType.MONTE_CARLO])
        
        # Weights should still sum to 1.0
        assert sum(recommendation_service.strategy_weights.values()) == pytest.approx(1.0)
        
        print(f"Updated weights: {recommendation_service.strategy_weights}")
    
    def test_time_filtering_integration(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test time-based filtering integration."""
        recommendation_service = RecommendationService(
            performance_calculator=PerformanceMetricsCalculator(),
            temporal_analyzer=TemporalAnalysisService(),
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator
        )
        
        # Generate recommendations for different times
        recommendations = []
        for hour in range(24):
            context = RecommendationContext(
                account_name="IPS_TM_10",
                symbol="NQ",
                current_time=datetime(2024, 1, 15, hour, 0),
                hour_of_day=hour,
                day_of_week=1,
                historical_trades=sample_trades,
                risk_tolerance=0.5
            )
            
            recommendation = recommendation_service.generate_recommendation(context)
            recommendations.append(recommendation)
        
        # Test filtering by favorable hours
        time_filters = {'allowed_hours': [10, 11, 14, 15]}
        filtered = recommendation_service.filter_recommendations_by_time(
            recommendations, time_filters
        )
        
        assert len(filtered) == 4
        assert all(r.hour_of_day in [10, 11, 14, 15] for r in filtered)
        
        # Test confidence filtering
        time_filters = {'min_confidence': 0.7}
        filtered = recommendation_service.filter_recommendations_by_time(
            recommendations, time_filters
        )
        
        assert all(r.confidence_score >= 0.7 for r in filtered)
        print(f"High confidence recommendations: {len(filtered)}/24")
    
    def test_error_handling_integration(self, sample_trades):
        """Test error handling in integrated system."""
        # Create service with failing components
        mock_prediction_service = Mock()
        mock_prediction_service.predict_optimal_conditions.side_effect = Exception("ML service failed")
        
        mock_monte_carlo = Mock()
        mock_monte_carlo.run_simulation.side_effect = Exception("Monte Carlo failed")
        
        recommendation_service = RecommendationService(
            performance_calculator=PerformanceMetricsCalculator(),
            temporal_analyzer=TemporalAnalysisService(),
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo,
            enable_parallel_strategies=False
        )
        
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime(2024, 1, 15, 14, 30),
            hour_of_day=14,
            day_of_week=1,
            historical_trades=sample_trades,
            risk_tolerance=0.5
        )
        
        # Should still generate recommendation despite failures
        recommendation = recommendation_service.generate_recommendation(context)
        
        assert isinstance(recommendation, TradingRecommendation)
        # Should fall back to statistical analysis only
        assert "Strategy failed" in recommendation.reasoning
    
    def test_performance_summary_integration(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test performance summary generation."""
        recommendation_service = RecommendationService(
            performance_calculator=PerformanceMetricsCalculator(),
            temporal_analyzer=TemporalAnalysisService(),
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator
        )
        
        # Generate some recommendations to build performance history
        for i in range(10):
            context = RecommendationContext(
                account_name="IPS_TM_10",
                symbol="NQ",
                current_time=datetime(2024, 1, 1) + timedelta(hours=i),
                hour_of_day=(9 + i) % 24,
                day_of_week=i % 7,
                historical_trades=sample_trades,
                risk_tolerance=0.5
            )
            
            recommendation_service.generate_recommendation(context)
        
        # Get performance summary
        summary = recommendation_service.get_strategy_performance_summary()
        
        assert isinstance(summary, dict)
        assert 'statistical' in summary
        assert 'machine_learning' in summary
        assert 'monte_carlo' in summary
        assert 'total_recommendations_generated' in summary
        
        print(f"Performance summary: {summary}")
    
    def test_real_temporal_analysis_integration(self, sample_trades):
        """Test integration with real temporal analysis service."""
        # Use real temporal analysis service
        temporal_analyzer = TemporalAnalysisService()
        
        # Analyze the sample trades
        analysis_result = temporal_analyzer.analyze_temporal_patterns(
            trades=sample_trades,
            account_name="IPS_TM_10",
            symbol="NQ"
        )
        
        # Verify analysis results
        assert len(analysis_result.hourly_patterns) == 24
        assert len(analysis_result.daily_patterns) == 7
        assert isinstance(analysis_result.best_hours, list)
        assert isinstance(analysis_result.best_days, list)
        
        # Should identify the patterns we built into the data
        print(f"Best hours identified: {analysis_result.best_hours}")
        print(f"Best days identified: {analysis_result.best_days}")
        
        # Hours 10, 11, 14, 15 should be in best hours (we made them profitable)
        favorable_hours_found = any(hour in analysis_result.best_hours for hour in [10, 11, 14, 15])
        assert favorable_hours_found, "Should identify some favorable hours from the pattern"
    
    def test_concurrent_recommendation_generation(self, sample_trades, mock_prediction_service, mock_monte_carlo_simulator):
        """Test concurrent recommendation generation."""
        recommendation_service = RecommendationService(
            performance_calculator=PerformanceMetricsCalculator(),
            temporal_analyzer=TemporalAnalysisService(),
            prediction_service=mock_prediction_service,
            monte_carlo_simulator=mock_monte_carlo_simulator,
            enable_parallel_strategies=True  # Enable parallel execution
        )
        
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime(2024, 1, 15, 14, 30),
            hour_of_day=14,
            day_of_week=1,
            historical_trades=sample_trades,
            risk_tolerance=0.5
        )
        
        # Generate recommendation with parallel strategies
        recommendation = recommendation_service.generate_recommendation(context)
        
        assert isinstance(recommendation, TradingRecommendation)
        assert recommendation.recommended_action in ['TRADE', 'AVOID']
        
        # Should have reasoning from multiple strategies
        assert len(recommendation.reasoning) > 50  # Should be comprehensive
        print(f"Parallel recommendation: {recommendation.recommended_action}")
        print(f"Reasoning length: {len(recommendation.reasoning)}")


if __name__ == '__main__':
    pytest.main([__file__])