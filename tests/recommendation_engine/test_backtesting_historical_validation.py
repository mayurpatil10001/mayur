"""
Historical validation tests for backtesting service.

This module tests the historical accuracy validation and strategy comparison
metrics for the backtesting framework.

Requirements: 6.1, 6.3
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from trading_platform.services.recommendation.backtesting_service import (
    BacktestingService, BacktestResult, StrategyComparisonResult, 
    BacktestConfiguration, ConfidenceScoring
)
from trading_platform.services.recommendation.recommendation_service import (
    StrategyType, StrategyResult, RecommendationContext, RecommendationService
)
from trading_platform.models.trading import ProcessedTrade, TradingRecommendation


@pytest.fixture
def historical_trades():
    """Create historical trades spanning multiple months for validation."""
    trades = []
    base_date = datetime(2023, 1, 1, 9, 0)
    
    # Create 6 months of trading data
    for month in range(6):
        for day in range(20):  # 20 trading days per month
            for trade_num in range(5):  # 5 trades per day
                trade_date = base_date + timedelta(days=month*30 + day, hours=trade_num)
                
                # Create realistic profit/loss patterns
                # Morning trades tend to be more profitable
                hour_factor = 1.2 if trade_date.hour < 12 else 0.8
                # Monday and Friday tend to be more volatile
                day_factor = 1.1 if trade_date.weekday() in [0, 4] else 0.9
                
                base_pnl = np.random.normal(5, 20) * hour_factor * day_factor
                
                trade = ProcessedTrade(
                    trade_id=f"hist_trade_{month}_{day}_{trade_num}",
                    account_name=f"IPS_TM_{10 + (trade_num % 3)}",  # 3 different accounts
                    symbol="NQ" if trade_num % 2 == 0 else "FDAX",
                    entry_time=trade_date,
                    exit_time=trade_date + timedelta(minutes=45),
                    entry_price=15000 + np.random.normal(0, 50),
                    exit_price=15000 + np.random.normal(0, 50),
                    quantity=1,
                    side="LONG" if trade_num % 3 != 0 else "SHORT",
                    profit_loss=base_pnl,
                    commission=2.5,
                    duration_minutes=45,
                    hour_of_day=trade_date.hour,
                    day_of_week=trade_date.weekday(),
                    entry_order_id=f"entry_{month}_{day}_{trade_num}",
                    exit_order_id=f"exit_{month}_{day}_{trade_num}"
                )
                trades.append(trade)
    
    return trades


@pytest.fixture
def validation_config():
    """Create configuration for historical validation."""
    return BacktestConfiguration(
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 6, 30),
        walk_forward_window=30,
        min_trades_required=10,
        confidence_level=0.95,
        enable_walk_forward=True,
        strategies_to_test=[StrategyType.STATISTICAL, StrategyType.MACHINE_LEARNING, StrategyType.MONTE_CARLO],
        parallel_execution=True,
        detailed_logging=True
    )


@pytest.fixture
def mock_recommendation_service_realistic():
    """Create realistic mock recommendation service for validation."""
    service = Mock(spec=RecommendationService)
    
    def statistical_strategy_mock(context):
        # Statistical strategy based on hour patterns
        if context.hour_of_day < 12:
            return StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='TRADE',
                confidence_score=0.75,
                expected_return=8.0,
                expected_risk=0.25,
                reasoning="Morning hours show statistical advantage",
                execution_time=0.1
            )
        else:
            return StrategyResult(
                strategy_type=StrategyType.STATISTICAL,
                recommendation='AVOID',
                confidence_score=0.65,
                expected_return=-2.0,
                expected_risk=0.35,
                reasoning="Afternoon hours show statistical disadvantage",
                execution_time=0.1
            )
    
    def ml_strategy_mock(context):
        # ML strategy with some randomness but bias toward profitable patterns
        profit_prob = 0.7 if context.day_of_week in [0, 4] else 0.4  # Monday/Friday bias
        
        if np.random.random() < profit_prob:
            return StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='TRADE',
                confidence_score=0.8,
                expected_return=12.0,
                expected_risk=0.3,
                reasoning="ML model predicts favorable conditions",
                execution_time=0.2
            )
        else:
            return StrategyResult(
                strategy_type=StrategyType.MACHINE_LEARNING,
                recommendation='AVOID',
                confidence_score=0.7,
                expected_return=-5.0,
                expected_risk=0.4,
                reasoning="ML model suggests avoiding trade",
                execution_time=0.2
            )
    
    def monte_carlo_strategy_mock(context):
        # Monte Carlo with conservative bias
        return StrategyResult(
            strategy_type=StrategyType.MONTE_CARLO,
            recommendation='TRADE' if np.random.random() < 0.3 else 'AVOID',
            confidence_score=0.6,
            expected_return=3.0,
            expected_risk=0.2,
            reasoning="Monte Carlo simulation shows moderate risk",
            execution_time=0.3
        )
    
    service._execute_statistical_strategy.side_effect = statistical_strategy_mock
    service._execute_ml_strategy.side_effect = ml_strategy_mock
    service._execute_monte_carlo_strategy.side_effect = monte_carlo_strategy_mock
    
    return service


class TestBacktestingHistoricalValidation:
    """Test cases for historical validation of backtesting service."""
    
    def test_historical_accuracy_validation(self, historical_trades, validation_config):
        """Test historical accuracy validation across strategies."""
        service = BacktestingService(enable_caching=False)
        
        # Run comprehensive backtest
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        # Validate results structure
        assert len(results) == len(validation_config.strategies_to_test)
        
        for strategy_type, result in results.items():
            assert isinstance(result, BacktestResult)
            assert result.strategy_type == strategy_type
            assert result.total_recommendations >= 0
            assert 0 <= result.accuracy <= 1
            assert result.execution_time >= 0
            
            # Validate statistical significance
            assert 'mean_return_t_test' in result.statistical_significance
            assert 'accuracy_binomial_test' in result.statistical_significance
    
    def test_strategy_comparison_with_historical_data(self, historical_trades, validation_config):
        """Test strategy comparison using historical data."""
        service = BacktestingService(enable_caching=False)
        
        # Run backtest
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        # Compare strategies
        comparisons = service.compare_strategies(results)
        
        # Should have pairwise comparisons
        expected_comparisons = len(validation_config.strategies_to_test) * (len(validation_config.strategies_to_test) - 1) // 2
        assert len(comparisons) == expected_comparisons
        
        for comparison in comparisons:
            assert isinstance(comparison, StrategyComparisonResult)
            assert comparison.strategy_a != comparison.strategy_b
            assert 0 <= comparison.t_test_pvalue <= 1
            assert 0 <= comparison.wilcoxon_pvalue <= 1
            assert 0 <= comparison.chi_square_pvalue <= 1
            assert comparison.statistical_significance in ['significant', 'not_significant', 'inconclusive']
    
    def test_confidence_scoring_historical_accuracy(self, historical_trades, validation_config):
        """Test confidence scoring based on historical accuracy."""
        service = BacktestingService(enable_caching=False)
        
        # Run backtest
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        # Update confidence scores
        for strategy_type, result in results.items():
            confidence_scoring = service.update_confidence_scoring(
                strategy_type=strategy_type,
                recent_accuracy=result.accuracy,
                sample_size=result.total_recommendations
            )
            
            assert isinstance(confidence_scoring, ConfidenceScoring)
            assert confidence_scoring.strategy_type == strategy_type
            assert 0.1 <= confidence_scoring.final_confidence <= 0.9
            assert confidence_scoring.sample_size == result.total_recommendations
            assert confidence_scoring.recent_accuracy == result.accuracy
    
    def test_walk_forward_validation_accuracy(self, historical_trades, validation_config):
        """Test walk-forward validation accuracy."""
        service = BacktestingService(enable_caching=False)
        
        # Enable walk-forward
        validation_config.enable_walk_forward = True
        validation_config.walk_forward_window = 30
        
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        # Walk-forward should provide more realistic accuracy estimates
        for strategy_type, result in results.items():
            # Should have reasonable number of predictions
            assert result.total_recommendations > 10
            
            # Accuracy should be within reasonable bounds
            assert 0.2 <= result.accuracy <= 0.8  # Not too perfect, not too bad
            
            # Should have confidence intervals
            assert 'mean_return' in result.confidence_intervals
            if 'sharpe_ratio' in result.confidence_intervals:
                ci = result.confidence_intervals['sharpe_ratio']
                assert len(ci) == 2
                assert ci[0] <= ci[1]
    
    def test_strategy_performance_report_validation(self, historical_trades, validation_config):
        """Test comprehensive strategy performance report."""
        service = BacktestingService(enable_caching=False)
        
        # Run backtest and comparisons
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        comparisons = service.compare_strategies(results)
        
        # Generate performance report
        report = service.generate_strategy_performance_report(results, comparisons)
        
        # Validate report structure
        assert 'timestamp' in report
        assert 'summary' in report
        assert 'individual_performance' in report
        assert 'strategy_comparisons' in report
        assert 'recommendations' in report
        
        # Validate summary
        summary = report['summary']
        assert summary['total_strategies_tested'] == len(results)
        assert summary['total_comparisons'] == len(comparisons)
        assert summary['best_strategy'] is not None
        assert summary['worst_strategy'] is not None
        
        # Validate individual performance
        for strategy_name, performance in report['individual_performance'].items():
            assert 'accuracy' in performance
            assert 'total_return' in performance
            assert 'sharpe_ratio' in performance
            assert 'confidence_intervals' in performance
            assert 'statistical_significance' in performance
        
        # Validate strategy comparisons
        for comparison_data in report['strategy_comparisons']:
            assert 'strategy_a' in comparison_data
            assert 'strategy_b' in comparison_data
            assert 'statistical_significance' in comparison_data
            assert 'p_values' in comparison_data
    
    def test_strategy_switching_validation(self, historical_trades, validation_config):
        """Test strategy switching logic with historical data."""
        service = BacktestingService(enable_caching=False)
        
        # Run backtest
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        comparisons = service.compare_strategies(results)
        
        # Test strategy switching
        original_strategy = service.current_best_strategy
        
        # Create performance data favoring statistical strategy
        performance_data = {
            StrategyType.STATISTICAL: 0.8,
            StrategyType.MACHINE_LEARNING: 0.6,
            StrategyType.MONTE_CARLO: 0.5
        }
        
        recommended_strategy = service.implement_strategy_switching(performance_data)
        
        # Should recommend best performing strategy
        assert recommended_strategy == StrategyType.STATISTICAL
        assert service.current_best_strategy == StrategyType.STATISTICAL
    
    def test_statistical_significance_validation(self, historical_trades, validation_config):
        """Test statistical significance calculations."""
        service = BacktestingService(enable_caching=False)
        
        # Run backtest
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        for strategy_type, result in results.items():
            # Check statistical significance tests
            sig_tests = result.statistical_significance
            
            if 'mean_return_t_test' in sig_tests:
                assert 0 <= sig_tests['mean_return_t_test'] <= 1
            
            if 'accuracy_binomial_test' in sig_tests:
                assert 0 <= sig_tests['accuracy_binomial_test'] <= 1
    
    def test_confidence_intervals_validation(self, historical_trades, validation_config):
        """Test confidence intervals calculation."""
        service = BacktestingService(enable_caching=False)
        
        # Run backtest
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        for strategy_type, result in results.items():
            if result.total_trades > 1:  # Need multiple trades for CI
                ci = result.confidence_intervals
                
                if 'mean_return' in ci:
                    lower, upper = ci['mean_return']
                    assert lower <= upper
                    assert lower <= result.avg_trade_return <= upper
    
    def test_multiple_account_symbol_validation(self, validation_config):
        """Test validation with multiple accounts and symbols."""
        # Create trades for multiple accounts and symbols
        trades = []
        base_date = datetime(2023, 1, 1, 9, 0)
        
        accounts = ["IPS_TM_10", "IPS_TM_11", "IPS_TM_12"]
        symbols = ["NQ", "FDAX"]
        
        for i in range(200):
            account = accounts[i % len(accounts)]
            symbol = symbols[i % len(symbols)]
            trade_date = base_date + timedelta(hours=i)
            
            # Different performance patterns for different accounts/symbols
            if account == "IPS_TM_10" and symbol == "NQ":
                base_pnl = np.random.normal(8, 15)  # Better performance
            elif account == "IPS_TM_11" and symbol == "FDAX":
                base_pnl = np.random.normal(3, 20)  # Moderate performance
            else:
                base_pnl = np.random.normal(-2, 25)  # Poor performance
            
            trade = ProcessedTrade(
                trade_id=f"multi_trade_{i}",
                account_name=account,
                symbol=symbol,
                entry_time=trade_date,
                exit_time=trade_date + timedelta(minutes=30),
                entry_price=15000 + np.random.normal(0, 50),
                exit_price=15000 + np.random.normal(0, 50),
                quantity=1,
                side="LONG" if i % 2 == 0 else "SHORT",
                profit_loss=base_pnl,
                commission=2.5,
                duration_minutes=30,
                hour_of_day=trade_date.hour,
                day_of_week=trade_date.weekday(),
                entry_order_id=f"entry_multi_{i}",
                exit_order_id=f"exit_multi_{i}"
            )
            trades.append(trade)
        
        service = BacktestingService(enable_caching=False)
        results = service.run_comprehensive_backtest(trades, validation_config)
        
        # Should handle multiple accounts/symbols correctly
        assert len(results) == len(validation_config.strategies_to_test)
        
        for result in results.values():
            assert result.total_recommendations > 0
            assert result.total_trades >= 0
    
    def test_edge_case_validation(self, validation_config):
        """Test validation with edge cases."""
        service = BacktestingService(enable_caching=False)
        
        # Test with minimal trades
        minimal_trades = []
        base_date = datetime(2023, 1, 1, 9, 0)
        
        for i in range(validation_config.min_trades_required):
            trade = ProcessedTrade(
                trade_id=f"minimal_trade_{i}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=base_date + timedelta(hours=i),
                exit_time=base_date + timedelta(hours=i, minutes=30),
                entry_price=15000.0,
                exit_price=15000.0 + (10 if i % 2 == 0 else -10),
                quantity=1,
                side="LONG",
                profit_loss=8.0 if i % 2 == 0 else -12.0,
                commission=2.0,
                duration_minutes=30,
                hour_of_day=(9 + i) % 24,
                day_of_week=i % 7,
                entry_order_id=f"entry_minimal_{i}",
                exit_order_id=f"exit_minimal_{i}"
            )
            minimal_trades.append(trade)
        
        results = service.run_comprehensive_backtest(minimal_trades, validation_config)
        
        # Should handle minimal data gracefully
        assert len(results) == len(validation_config.strategies_to_test)
        
        for result in results.values():
            assert result.total_recommendations >= 0
            assert 0 <= result.accuracy <= 1
    
    def test_performance_degradation_detection(self, historical_trades, validation_config):
        """Test detection of performance degradation over time."""
        service = BacktestingService(enable_caching=False)
        
        # Split data into early and late periods
        mid_date = datetime(2023, 3, 15)
        early_trades = [t for t in historical_trades if t.entry_time < mid_date]
        late_trades = [t for t in historical_trades if t.entry_time >= mid_date]
        
        # Run backtests on both periods
        early_config = BacktestConfiguration(
            start_date=datetime(2023, 1, 1),
            end_date=mid_date,
            walk_forward_window=30,
            min_trades_required=10,
            confidence_level=0.95,
            enable_walk_forward=True,
            strategies_to_test=[StrategyType.STATISTICAL, StrategyType.MACHINE_LEARNING],
            parallel_execution=False
        )
        
        late_config = BacktestConfiguration(
            start_date=mid_date,
            end_date=datetime(2023, 6, 30),
            walk_forward_window=30,
            min_trades_required=10,
            confidence_level=0.95,
            enable_walk_forward=True,
            strategies_to_test=[StrategyType.STATISTICAL, StrategyType.MACHINE_LEARNING],
            parallel_execution=False
        )
        
        early_results = service.run_comprehensive_backtest(early_trades, early_config)
        late_results = service.run_comprehensive_backtest(late_trades, late_config)
        
        # Compare performance between periods
        for strategy_type in [StrategyType.STATISTICAL, StrategyType.MACHINE_LEARNING]:
            if strategy_type in early_results and strategy_type in late_results:
                early_accuracy = early_results[strategy_type].accuracy
                late_accuracy = late_results[strategy_type].accuracy
                
                # Calculate performance change
                performance_change = late_accuracy - early_accuracy
                
                # Should be able to detect significant changes
                assert isinstance(performance_change, float)
                assert -1.0 <= performance_change <= 1.0
    
    @pytest.mark.parametrize("confidence_level", [0.90, 0.95, 0.99])
    def test_confidence_level_validation(self, historical_trades, validation_config, confidence_level):
        """Test validation with different confidence levels."""
        validation_config.confidence_level = confidence_level
        
        service = BacktestingService(enable_caching=False)
        results = service.run_comprehensive_backtest(historical_trades, validation_config)
        
        for result in results.values():
            if result.total_trades > 1:
                # Confidence intervals should reflect the confidence level
                ci = result.confidence_intervals
                if 'mean_return' in ci:
                    lower, upper = ci['mean_return']
                    interval_width = upper - lower
                    
                    # Higher confidence should generally mean wider intervals
                    assert interval_width >= 0
    
    def test_caching_with_historical_data(self, historical_trades, validation_config):
        """Test caching functionality with historical data."""
        service = BacktestingService(enable_caching=True, cache_duration_hours=1)
        
        # First run
        start_time = datetime.now()
        results1 = service.run_comprehensive_backtest(historical_trades, validation_config)
        first_run_time = datetime.now() - start_time
        
        # Second run (should be cached)
        start_time = datetime.now()
        results2 = service.run_comprehensive_backtest(historical_trades, validation_config)
        second_run_time = datetime.now() - start_time
        
        # Results should be identical
        assert len(results1) == len(results2)
        for strategy_type in results1:
            assert strategy_type in results2
            # Note: Due to the nature of the objects, we compare key metrics
            assert results1[strategy_type].accuracy == results2[strategy_type].accuracy
            assert results1[strategy_type].total_return == results2[strategy_type].total_return
        
        # Second run should be faster (cached)
        assert second_run_time < first_run_time
        
        # Cache should contain the results
        assert len(service.backtest_cache) == 1