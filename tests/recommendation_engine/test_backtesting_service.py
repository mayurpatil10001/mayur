"""
Unit tests for backtesting service.

This module tests the backtesting service functionality including
strategy comparison, performance tracking, and confidence scoring.

Requirements: 6.1, 6.3
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from trading_platform.models.trading import ProcessedTrade, TradingRecommendation
from trading_platform.services.recommendation.backtesting_service import (
    BacktestingService, BacktestResult, StrategyComparisonResult, 
    BacktestConfiguration, ConfidenceScoring
)
from trading_platform.services.recommendation.recommendation_service import (
    StrategyType, StrategyResult, RecommendationContext, RecommendationService
)


class TestBacktestingService:
    """Test cases for BacktestingService."""
    
    @pytest.fixture
    def sample_trades(self) -> List[ProcessedTrade]:
        """Create sample trades for testing."""
        trades = []
        base_time = datetime(2024, 1, 1, 9, 0)
        
        for i in range(50):
            trade = ProcessedTrade(
                trade_id=f"trade_{i}",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=base_time + timedelta(hours=i),
                exit_time=base_time + timedelta(hours=i, minutes=30),
                entry_price=15000.0 + i * 10,
                exit_price=15000.0 + i * 10 + (10 if i % 2 == 0 else -5),  # Alternating wins/losses
                quantity=1,
                side="LONG",
                profit_loss=8.0 if i % 2 == 0 else -7.0,  # Adjusted for commission
                commission=2.0,
                duration_minutes=30,
                hour_of_day=(9 + i) % 24,
                day_of_week=i % 7,
                entry_order_id=f"entry_{i}",
                exit_order_id=f"exit_{i}"
            )
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def backtest_config(self) -> BacktestConfiguration:
        """Create backtest configuration for testing."""
        return BacktestConfiguration(
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 10),
            walk_forward_window=5,
            min_trades_required=5,
            confidence_level=0.95,
            enable_walk_forward=True,
            strategies_to_test=[StrategyType.STATISTICAL, StrategyType.MACHINE_LEARNING],
            parallel_execution=False,
            detailed_logging=True
        )
    
    @pytest.fixture
    def mock_recommendation_service(self) -> Mock:
        """Create mock recommendation service."""
        service = Mock(spec=RecommendationService)
        
        # Mock strategy execution methods
        service._execute_statistical_strategy.return_value = StrategyResult(
            strategy_type=StrategyType.STATISTICAL,
            recommendation='TRADE',
            confidence_score=0.7,
            expected_return=5.0,
            expected_risk=0.3,
            reasoning="Statistical analysis favorable",
            execution_time=0.1
        )
        
        service._execute_ml_strategy.return_value = StrategyResult(
            strategy_type=StrategyType.MACHINE_LEARNING,
            recommendation='AVOID',
            confidence_score=0.6,
            expected_return=-2.0,
            expected_risk=0.4,
            reasoning="ML model suggests avoiding",
            execution_time=0.2
        )
        
        service._execute_monte_carlo_strategy.return_value = StrategyResult(
            strategy_type=StrategyType.MONTE_CARLO,
            recommendation='TRADE',
            confidence_score=0.8,
            expected_return=8.0,
            expected_risk=0.2,
            reasoning="Monte Carlo simulation favorable",
            execution_time=0.3
        )
        
        return service
    
    @pytest.fixture
    def backtesting_service(self, mock_recommendation_service) -> BacktestingService:
        """Create backtesting service for testing."""
        return BacktestingService(
            recommendation_service=mock_recommendation_service,
            enable_caching=False
        )
    
    def test_initialization(self, mock_recommendation_service):
        """Test backtesting service initialization."""
        service = BacktestingService(
            recommendation_service=mock_recommendation_service,
            enable_caching=True,
            cache_duration_hours=12
        )
        
        assert service.recommendation_service == mock_recommendation_service
        assert service.enable_caching is True
        assert service.cache_duration == timedelta(hours=12)
        assert len(service.strategy_performance_history) == len(StrategyType)
        assert service.strategy_switching_enabled is True
    
    def test_run_comprehensive_backtest_success(self, backtesting_service, sample_trades, backtest_config):
        """Test successful comprehensive backtesting."""
        results = backtesting_service.run_comprehensive_backtest(sample_trades, backtest_config)
        
        assert isinstance(results, dict)
        assert len(results) == len(backtest_config.strategies_to_test)
        
        for strategy_type in backtest_config.strategies_to_test:
            assert strategy_type in results
            result = results[strategy_type]
            assert isinstance(result, BacktestResult)
            assert result.strategy_type == strategy_type
            assert result.total_recommendations > 0
            assert 0 <= result.accuracy <= 1
            assert result.execution_time >= 0
    
    def test_run_comprehensive_backtest_insufficient_trades(self, backtesting_service, backtest_config):
        """Test backtesting with insufficient trades."""
        few_trades = [
            ProcessedTrade(
                trade_id="trade_1",
                account_name="IPS_TM_10",
                symbol="NQ",
                entry_time=datetime(2024, 1, 1, 9, 0),
                exit_time=datetime(2024, 1, 1, 9, 30),
                entry_price=15000.0,
                exit_price=15010.0,
                quantity=1,
                side="LONG",
                profit_loss=8.0,  # 10.0 - 2.0 commission
                commission=2.0,
                duration_minutes=30,
                hour_of_day=9,
                day_of_week=0,
                entry_order_id="entry_1",
                exit_order_id="exit_1"
            )
        ]
        
        with pytest.raises(ValueError, match="Insufficient trades"):
            backtesting_service.run_comprehensive_backtest(few_trades, backtest_config)
    
    def test_run_comprehensive_backtest_empty_trades(self, backtesting_service, backtest_config):
        """Test backtesting with empty trades list."""
        with pytest.raises(ValueError, match="No trades provided"):
            backtesting_service.run_comprehensive_backtest([], backtest_config)
    
    def test_backtest_single_strategy_statistical(self, backtesting_service, sample_trades, backtest_config):
        """Test backtesting single statistical strategy."""
        result = backtesting_service._backtest_single_strategy(
            StrategyType.STATISTICAL, sample_trades, backtest_config
        )
        
        assert isinstance(result, BacktestResult)
        assert result.strategy_type == StrategyType.STATISTICAL
        assert result.total_recommendations >= 0
        assert result.total_trades >= 0
        assert 0 <= result.accuracy <= 1
        assert 0 <= result.win_rate <= 1
        assert result.profit_factor >= 0
        assert result.execution_time >= 0
        assert isinstance(result.confidence_intervals, dict)
        assert isinstance(result.statistical_significance, dict)
    
    def test_backtest_single_strategy_machine_learning(self, backtesting_service, sample_trades, backtest_config):
        """Test backtesting single ML strategy."""
        result = backtesting_service._backtest_single_strategy(
            StrategyType.MACHINE_LEARNING, sample_trades, backtest_config
        )
        
        assert isinstance(result, BacktestResult)
        assert result.strategy_type == StrategyType.MACHINE_LEARNING
        assert result.total_recommendations >= 0
        assert result.total_trades >= 0  # ML might recommend avoiding all trades
        assert 0 <= result.accuracy <= 1
    
    def test_walk_forward_backtest(self, backtesting_service, sample_trades, backtest_config):
        """Test walk-forward backtesting."""
        trade_groups = {("IPS_TM_10", "NQ"): sample_trades}
        
        predictions, outcomes, returns = backtesting_service._walk_forward_backtest(
            StrategyType.STATISTICAL, backtest_config, trade_groups
        )
        
        assert len(predictions) == len(outcomes)
        assert all(pred in ['TRADE', 'AVOID'] for pred in predictions)
        assert all(isinstance(outcome, (int, float)) for outcome in outcomes)
        assert all(isinstance(ret, (int, float)) for ret in returns)
    
    def test_simple_backtest(self, backtesting_service, sample_trades, backtest_config):
        """Test simple backtesting without walk-forward."""
        backtest_config.enable_walk_forward = False
        trade_groups = {("IPS_TM_10", "NQ"): sample_trades}
        
        predictions, outcomes, returns = backtesting_service._simple_backtest(
            StrategyType.STATISTICAL, backtest_config, trade_groups
        )
        
        assert len(predictions) == len(outcomes)
        assert len(predictions) > 0  # Should have some predictions
    
    def test_generate_strategy_prediction(self, backtesting_service):
        """Test strategy prediction generation."""
        context = RecommendationContext(
            account_name="IPS_TM_10",
            symbol="NQ",
            current_time=datetime(2024, 1, 1, 10, 0),
            hour_of_day=10,
            day_of_week=0,
            historical_trades=[],
            risk_tolerance=0.5
        )
        
        # Test statistical strategy
        prediction = backtesting_service._generate_strategy_prediction(
            StrategyType.STATISTICAL, context
        )
        assert prediction in ['TRADE', 'AVOID']
        
        # Test ML strategy
        prediction = backtesting_service._generate_strategy_prediction(
            StrategyType.MACHINE_LEARNING, context
        )
        assert prediction in ['TRADE', 'AVOID']
    
    def test_compare_strategies(self, backtesting_service):
        """Test strategy comparison."""
        # Create mock backtest results
        result_a = BacktestResult(
            strategy_type=StrategyType.STATISTICAL,
            total_recommendations=100,
            correct_predictions=70,
            accuracy=0.7,
            total_return=150.0,
            win_rate=0.6,
            profit_factor=1.5,
            max_drawdown=-50.0,
            sharpe_ratio=1.2,
            volatility=20.0,
            avg_trade_return=1.5,
            best_trade=25.0,
            worst_trade=-15.0,
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            avg_winning_trade=4.0,
            avg_losing_trade=-2.0,
            execution_time=1.0,
            confidence_intervals={'mean': (1.0, 2.0), 'std': (18.0, 22.0)},
            statistical_significance={'t_test_pvalue': 0.01, 'normality_test_pvalue': 0.1}
        )
        
        result_b = BacktestResult(
            strategy_type=StrategyType.MACHINE_LEARNING,
            total_recommendations=100,
            correct_predictions=65,
            accuracy=0.65,
            total_return=120.0,
            win_rate=0.55,
            profit_factor=1.3,
            max_drawdown=-60.0,
            sharpe_ratio=1.0,
            volatility=25.0,
            avg_trade_return=1.2,
            best_trade=20.0,
            worst_trade=-18.0,
            total_trades=100,
            winning_trades=55,
            losing_trades=45,
            avg_winning_trade=3.5,
            avg_losing_trade=-2.5,
            execution_time=1.5,
            confidence_intervals={'mean': (0.8, 1.6), 'std': (23.0, 27.0)},
            statistical_significance={'t_test_pvalue': 0.05, 'normality_test_pvalue': 0.2}
        )
        
        backtest_results = {
            StrategyType.STATISTICAL: result_a,
            StrategyType.MACHINE_LEARNING: result_b
        }
        
        comparisons = backtesting_service.compare_strategies(backtest_results)
        
        assert len(comparisons) == 1
        comparison = comparisons[0]
        assert isinstance(comparison, StrategyComparisonResult)
        assert comparison.strategy_a == StrategyType.STATISTICAL
        assert comparison.strategy_b == StrategyType.MACHINE_LEARNING
        assert comparison.accuracy_difference == 0.05  # 0.7 - 0.65
        assert comparison.return_difference == 30.0  # 150 - 120
        assert comparison.statistical_significance in ['significant', 'not_significant', 'inconclusive']
    
    def test_generate_strategy_performance_report(self, backtesting_service):
        """Test strategy performance report generation."""
        # Create mock results and comparisons
        backtest_results = {
            StrategyType.STATISTICAL: BacktestResult(
                strategy_type=StrategyType.STATISTICAL,
                total_recommendations=100, correct_predictions=70, accuracy=0.7,
                total_return=150.0, win_rate=0.6, profit_factor=1.5,
                max_drawdown=-50.0, sharpe_ratio=1.2, volatility=20.0,
                avg_trade_return=1.5, best_trade=25.0, worst_trade=-15.0,
                total_trades=100, winning_trades=60, losing_trades=40,
                avg_winning_trade=4.0, avg_losing_trade=-2.0, execution_time=1.0,
                confidence_intervals={'mean': (1.0, 2.0)},
                statistical_significance={'t_test_pvalue': 0.01}
            )
        }
        
        comparisons = []
        
        report = backtesting_service.generate_strategy_performance_report(
            backtest_results, comparisons
        )
        
        assert 'summary' in report
        assert 'individual_performance' in report
        assert 'strategy_rankings' in report
        assert 'statistical_comparisons' in report
        assert 'recommendations' in report
        
        assert report['summary']['total_strategies_tested'] == 1
        assert 'statistical' in report['individual_performance']
        assert report['individual_performance']['statistical']['accuracy'] == 0.7
    
    def test_update_confidence_scoring(self, backtesting_service):
        """Test confidence scoring update."""
        backtest_results = {
            StrategyType.STATISTICAL: BacktestResult(
                strategy_type=StrategyType.STATISTICAL,
                total_recommendations=100, correct_predictions=70, accuracy=0.7,
                total_return=150.0, win_rate=0.6, profit_factor=1.5,
                max_drawdown=-50.0, sharpe_ratio=1.2, volatility=20.0,
                avg_trade_return=1.5, best_trade=25.0, worst_trade=-15.0,
                total_trades=100, winning_trades=60, losing_trades=40,
                avg_winning_trade=4.0, avg_losing_trade=-2.0, execution_time=1.0,
                confidence_intervals={'mean': (1.0, 2.0)},
                statistical_significance={'t_test_pvalue': 0.01}
            )
        }
        
        confidence_scores = backtesting_service.update_confidence_scoring(backtest_results)
        
        assert StrategyType.STATISTICAL in confidence_scores
        scoring = confidence_scores[StrategyType.STATISTICAL]
        assert isinstance(scoring, ConfidenceScoring)
        assert scoring.strategy_type == StrategyType.STATISTICAL
        assert 0.1 <= scoring.final_confidence <= 0.9
        assert scoring.sample_size == 100
    
    def test_implement_strategy_switching(self, backtesting_service):
        """Test strategy switching logic."""
        # Create comparison that favors statistical strategy
        comparison = StrategyComparisonResult(
            strategy_a=StrategyType.STATISTICAL,
            strategy_b=StrategyType.MACHINE_LEARNING,
            strategy_a_performance=Mock(),
            strategy_b_performance=Mock(),
            accuracy_difference=0.1,
            return_difference=50.0,
            risk_difference=-5.0,
            sharpe_difference=0.3,
            t_test_pvalue=0.01,
            wilcoxon_pvalue=0.02,
            chi_square_pvalue=0.03,
            preference_score=0.15,  # Above switching threshold
            statistical_significance='significant',
            sample_size=100
        )
        
        # Set current strategy to ML
        backtesting_service.current_best_strategy = StrategyType.MACHINE_LEARNING
        
        recommended_strategy = backtesting_service.implement_strategy_switching([comparison])
        
        assert recommended_strategy == StrategyType.STATISTICAL
        assert backtesting_service.current_best_strategy == StrategyType.STATISTICAL
    
    def test_implement_strategy_switching_no_change(self, backtesting_service):
        """Test strategy switching when no change is needed."""
        # Create comparison with small difference
        comparison = StrategyComparisonResult(
            strategy_a=StrategyType.STATISTICAL,
            strategy_b=StrategyType.MACHINE_LEARNING,
            strategy_a_performance=Mock(),
            strategy_b_performance=Mock(),
            accuracy_difference=0.01,
            return_difference=5.0,
            risk_difference=1.0,
            sharpe_difference=0.05,
            t_test_pvalue=0.1,
            wilcoxon_pvalue=0.15,
            chi_square_pvalue=0.2,
            preference_score=0.05,  # Below switching threshold
            statistical_significance='not_significant',
            sample_size=100
        )
        
        original_strategy = backtesting_service.current_best_strategy
        recommended_strategy = backtesting_service.implement_strategy_switching([comparison])
        
        assert recommended_strategy is None
        assert backtesting_service.current_best_strategy == original_strategy
    
    def test_get_confidence_score(self, backtesting_service):
        """Test getting confidence score for strategy."""
        # Test default confidence
        confidence = backtesting_service.get_confidence_score(StrategyType.STATISTICAL)
        assert confidence == 0.5  # Default
        
        # Set a confidence score
        backtesting_service.confidence_scores[StrategyType.STATISTICAL] = ConfidenceScoring(
            strategy_type=StrategyType.STATISTICAL,
            base_confidence=0.5,
            historical_accuracy=0.7,
            recent_accuracy=0.75,
            confidence_adjustment=0.1,
            final_confidence=0.8,
            sample_size=100
        )
        
        confidence = backtesting_service.get_confidence_score(StrategyType.STATISTICAL)
        assert confidence == 0.8
    
    def test_get_strategy_switching_recommendation(self, backtesting_service):
        """Test getting strategy switching recommendation."""
        recommendation = backtesting_service.get_strategy_switching_recommendation()
        
        assert 'current_best_strategy' in recommendation
        assert 'switching_enabled' in recommendation
        assert 'switching_threshold' in recommendation
        assert 'confidence_scores' in recommendation
        
        assert recommendation['switching_enabled'] is True
        assert recommendation['switching_threshold'] == 0.1
        assert len(recommendation['confidence_scores']) == len(StrategyType)
    
    def test_caching_functionality(self, mock_recommendation_service, sample_trades, backtest_config):
        """Test caching functionality."""
        service = BacktestingService(
            recommendation_service=mock_recommendation_service,
            enable_caching=True,
            cache_duration_hours=1
        )
        
        # First call should compute results
        results1 = service.run_comprehensive_backtest(sample_trades, backtest_config)
        
        # Second call should return cached results
        results2 = service.run_comprehensive_backtest(sample_trades, backtest_config)
        
        assert results1 == results2
        assert len(service.backtest_cache) == 1
    
    def test_parallel_vs_sequential_execution(self, backtesting_service, sample_trades, backtest_config):
        """Test parallel vs sequential execution."""
        # Test sequential
        backtest_config.parallel_execution = False
        results_sequential = backtesting_service.run_comprehensive_backtest(sample_trades, backtest_config)
        
        # Test parallel
        backtest_config.parallel_execution = True
        results_parallel = backtesting_service.run_comprehensive_backtest(sample_trades, backtest_config)
        
        # Results should be similar (allowing for small differences due to randomness)
        assert len(results_sequential) == len(results_parallel)
        for strategy in results_sequential:
            assert strategy in results_parallel
    
    def test_statistical_tests(self, backtesting_service):
        """Test statistical test methods."""
        result_a = BacktestResult(
            strategy_type=StrategyType.STATISTICAL,
            total_recommendations=100, correct_predictions=70, accuracy=0.7,
            total_return=150.0, win_rate=0.6, profit_factor=1.5,
            max_drawdown=-50.0, sharpe_ratio=1.2, volatility=20.0,
            avg_trade_return=1.5, best_trade=25.0, worst_trade=-15.0,
            total_trades=100, winning_trades=60, losing_trades=40,
            avg_winning_trade=4.0, avg_losing_trade=-2.0, execution_time=1.0,
            confidence_intervals={'mean': (1.0, 2.0)},
            statistical_significance={'t_test_pvalue': 0.01}
        )
        
        result_b = BacktestResult(
            strategy_type=StrategyType.MACHINE_LEARNING,
            total_recommendations=100, correct_predictions=65, accuracy=0.65,
            total_return=120.0, win_rate=0.55, profit_factor=1.3,
            max_drawdown=-60.0, sharpe_ratio=1.0, volatility=25.0,
            avg_trade_return=1.2, best_trade=20.0, worst_trade=-18.0,
            total_trades=100, winning_trades=55, losing_trades=45,
            avg_winning_trade=3.5, avg_losing_trade=-2.5, execution_time=1.5,
            confidence_intervals={'mean': (0.8, 1.6)},
            statistical_significance={'t_test_pvalue': 0.05}
        )
        
        # Test t-test
        t_pvalue = backtesting_service._perform_t_test(result_a, result_b)
        assert 0 <= t_pvalue <= 1
        
        # Test Wilcoxon test
        wilcoxon_pvalue = backtesting_service._perform_wilcoxon_test(result_a, result_b)
        assert 0 <= wilcoxon_pvalue <= 1
        
        # Test chi-square test
        chi_pvalue = backtesting_service._perform_chi_square_test(result_a, result_b)
        assert 0 <= chi_pvalue <= 1
    
    def test_confidence_intervals_calculation(self, backtesting_service):
        """Test confidence intervals calculation."""
        returns = np.array([1.0, 2.0, -1.0, 3.0, 0.5, -0.5, 2.5, 1.5])
        
        ci = backtesting_service._calculate_confidence_intervals(returns, 0.95)
        
        assert 'mean' in ci
        assert 'std' in ci
        assert len(ci['mean']) == 2
        assert len(ci['std']) == 2
        assert ci['mean'][0] <= ci['mean'][1]  # Lower bound <= upper bound
        assert ci['std'][0] <= ci['std'][1]
    
    def test_statistical_significance_calculation(self, backtesting_service):
        """Test statistical significance calculation."""
        returns = np.array([1.0, 2.0, -1.0, 3.0, 0.5, -0.5, 2.5, 1.5])
        
        sig = backtesting_service._calculate_statistical_significance(returns)
        
        assert 't_test_pvalue' in sig
        assert 'normality_test_pvalue' in sig
        assert 0 <= sig['t_test_pvalue'] <= 1
        assert 0 <= sig['normality_test_pvalue'] <= 1
    
    def test_error_handling(self, backtesting_service, backtest_config):
        """Test error handling in various scenarios."""
        # Test with invalid strategy type
        with pytest.raises(ValueError):
            backtesting_service._generate_strategy_prediction(
                "INVALID_STRATEGY", Mock()
            )
        
        # Test with empty trade groups
        empty_groups = {}
        predictions, outcomes, returns = backtesting_service._walk_forward_backtest(
            StrategyType.STATISTICAL, empty_groups, backtest_config
        )
        assert len(predictions) == 0
        assert len(outcomes) == 0
        assert len(returns) == 0
    
    @patch('trading_platform.services.recommendation.backtesting_service.ThreadPoolExecutor')
    def test_parallel_execution_with_failures(self, mock_executor, backtesting_service, sample_trades, backtest_config):
        """Test parallel execution handling failures."""
        # Mock executor to simulate failures
        mock_future = Mock()
        mock_future.result.side_effect = Exception("Strategy execution failed")
        
        mock_executor_instance = Mock()
        mock_executor_instance.__enter__.return_value = mock_executor_instance
        mock_executor_instance.__exit__.return_value = None
        mock_executor_instance.submit.return_value = mock_future
        mock_executor.return_value = mock_executor_instance
        
        # Mock as_completed to return our mock future
        with patch('trading_platform.services.recommendation.backtesting_service.as_completed') as mock_as_completed:
            mock_as_completed.return_value = [mock_future]
            
            backtest_config.parallel_execution = True
            results = backtesting_service._run_parallel_backtests(sample_trades, backtest_config)
            
            # Should handle failures gracefully
            assert isinstance(results, dict)