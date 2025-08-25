"""
Test suite for OutOfSampleValidator - Walk-Forward Analysis.

Comprehensive testing of walk-forward analysis methods including anchored,
rolling window, expanding window validation, and time-series cross-validation
for strategy robustness testing and overfitting detection.

Requirements: 2.1, 2.6, 14.1
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from trading_platform.services.walk_forward.out_of_sample_validator import (
    OutOfSampleValidator,
    WalkForwardValidationRequest,
    WalkForwardValidationResult,
    PeriodPerformance,
    ValidationMethodEnum,
    RobustnessTestConfig,
    CrossValidationConfig,
    PerformanceMetrics
)
from trading_platform.services.time_bin_analyzer import TimeBin
from trading_platform.models.models import ProcessedTrade


class TestOutOfSampleValidator:
    """Test suite for OutOfSampleValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create OutOfSampleValidator instance."""
        return OutOfSampleValidator()
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data for testing."""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        for i in range(100):
            trade = Mock(spec=ProcessedTrade)
            trade.trade_id = i + 1
            trade.account_name = "TEST_ACCOUNT"
            trade.entry_time = base_date + timedelta(days=i, minutes=i*5)
            trade.exit_time = base_date + timedelta(days=i, minutes=i*5 + 30)
            trade.quantity = 100 + i
            trade.entry_price = 100.0 + np.random.uniform(-5, 5)
            trade.exit_price = trade.entry_price + np.random.uniform(-2, 3)
            trade.gross_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            trade.net_pnl = trade.gross_pnl - 2.5  # Commission
            trade.mae = abs(np.random.uniform(0, 2))
            trade.mfe = abs(np.random.uniform(0, 4))
            trade.duration_minutes = 30
            trade.time_bin = TimeBin.HOUR_9_MINUTE_30
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def validation_request(self):
        """Create sample validation request."""
        return WalkForwardValidationRequest(
            account_name="TEST_ACCOUNT",
            start_date="2024-01-01",
            end_date="2024-06-30",
            time_bin=TimeBin.HOUR_9_MINUTE_30,
            validation_method=ValidationMethodEnum.ANCHORED_WALK_FORWARD,
            min_in_sample_days=30,
            out_of_sample_days=10,
            step_days=5,
            robustness_config=RobustnessTestConfig(
                min_trades_threshold=10,
                performance_stability_threshold=0.3,
                overfitting_detection_threshold=0.5,
                confidence_level=0.95
            )
        )
    
    @pytest.fixture
    def sample_performance_metrics(self):
        """Create sample performance metrics."""
        return PerformanceMetrics(
            total_trades=50,
            winning_trades=32,
            losing_trades=18,
            win_rate=0.64,
            average_pnl=125.50,
            total_pnl=6275.0,
            average_winner=250.75,
            average_loser=-98.33,
            largest_winner=850.0,
            largest_loser=-275.0,
            profit_factor=2.58,
            sharpe_ratio=1.45,
            max_drawdown_pct=8.5,
            max_consecutive_losses=3,
            total_commission=125.0,
            avg_trade_duration_minutes=28.5,
            longest_drawdown_period_days=5,
            calmar_ratio=0.171
        )
    
    @pytest.fixture
    def mock_strategy_service(self):
        """Mock strategy service for testing."""
        service = Mock()
        service.generate_signals.return_value = [1, -1, 0, 1, 1, -1, 0, 1]
        service.backtest_strategy.return_value = Mock()
        return service


class TestValidationMethods:
    """Test individual validation methods."""
    
    def test_anchored_walk_forward_success(self, validator, validation_request, 
                                          sample_trades, sample_performance_metrics):
        """Test anchored walk-forward validation."""
        
        # Mock dependencies
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = sample_trades[:20]  # Sample subset
            
            with patch.object(validator, '_calculate_period_performance') as mock_calc_perf:
                mock_period_perf = Mock(spec=PeriodPerformance)
                mock_period_perf.period_id = "period_1"
                mock_period_perf.in_sample_start = datetime(2024, 1, 1)
                mock_period_perf.in_sample_end = datetime(2024, 1, 31)
                mock_period_perf.out_of_sample_start = datetime(2024, 2, 1)
                mock_period_perf.out_of_sample_end = datetime(2024, 2, 10)
                mock_period_perf.in_sample_metrics = sample_performance_metrics
                mock_period_perf.out_of_sample_metrics = sample_performance_metrics
                mock_period_perf.trades_count_in_sample = 15
                mock_period_perf.trades_count_out_of_sample = 5
                
                mock_calc_perf.return_value = mock_period_perf
                
                # Run anchored walk-forward
                result = validator.anchored_walk_forward(validation_request)
                
                # Verify result structure
                assert isinstance(result, WalkForwardValidationResult)
                assert result.validation_method == ValidationMethodEnum.ANCHORED_WALK_FORWARD
                assert result.request.account_name == "TEST_ACCOUNT"
                assert len(result.period_performances) > 0
                assert result.overall_metrics is not None
                assert result.stability_analysis is not None
                assert result.recommendation is not None
                
                # Verify methods were called
                assert mock_get_trades.called
                assert mock_calc_perf.called
    
    def test_rolling_window_validation_success(self, validator, validation_request, 
                                             sample_trades, sample_performance_metrics):
        """Test rolling window validation."""
        
        # Modify request for rolling window
        validation_request.validation_method = ValidationMethodEnum.ROLLING_WINDOW
        
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = sample_trades[:20]
            
            with patch.object(validator, '_calculate_period_performance') as mock_calc_perf:
                mock_period_perf = Mock(spec=PeriodPerformance)
                mock_period_perf.period_id = "rolling_1"
                mock_period_perf.in_sample_start = datetime(2024, 1, 1)
                mock_period_perf.in_sample_end = datetime(2024, 1, 31)
                mock_period_perf.out_of_sample_start = datetime(2024, 2, 1)
                mock_period_perf.out_of_sample_end = datetime(2024, 2, 10)
                mock_period_perf.in_sample_metrics = sample_performance_metrics
                mock_period_perf.out_of_sample_metrics = sample_performance_metrics
                mock_period_perf.trades_count_in_sample = 15
                mock_period_perf.trades_count_out_of_sample = 5
                
                mock_calc_perf.return_value = mock_period_perf
                
                result = validator.rolling_window_validation(validation_request)
                
                assert result.validation_method == ValidationMethodEnum.ROLLING_WINDOW
                assert len(result.period_performances) > 0
                assert result.overall_metrics is not None
    
    def test_expanding_window_validation_success(self, validator, validation_request, 
                                               sample_trades, sample_performance_metrics):
        """Test expanding window validation."""
        
        validation_request.validation_method = ValidationMethodEnum.EXPANDING_WINDOW
        
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = sample_trades[:30]
            
            with patch.object(validator, '_calculate_period_performance') as mock_calc_perf:
                mock_period_perf = Mock(spec=PeriodPerformance)
                mock_period_perf.period_id = "expanding_1"
                mock_period_perf.in_sample_start = datetime(2024, 1, 1)
                mock_period_perf.in_sample_end = datetime(2024, 2, 15)  # Expanding window
                mock_period_perf.out_of_sample_start = datetime(2024, 2, 16)
                mock_period_perf.out_of_sample_end = datetime(2024, 2, 26)
                mock_period_perf.in_sample_metrics = sample_performance_metrics
                mock_period_perf.out_of_sample_metrics = sample_performance_metrics
                mock_period_perf.trades_count_in_sample = 25
                mock_period_perf.trades_count_out_of_sample = 5
                
                mock_calc_perf.return_value = mock_period_perf
                
                result = validator.expanding_window_validation(validation_request)
                
                assert result.validation_method == ValidationMethodEnum.EXPANDING_WINDOW
                assert len(result.period_performances) > 0
    
    def test_time_series_cross_validation_success(self, validator, validation_request, 
                                                 sample_trades, sample_performance_metrics):
        """Test time-series cross-validation."""
        
        # Create CV config
        cv_config = CrossValidationConfig(
            n_splits=5,
            test_size_ratio=0.2,
            gap_days=2,
            shuffle=False,
            random_seed=42
        )
        
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = sample_trades
            
            with patch.object(validator, '_calculate_period_performance') as mock_calc_perf:
                mock_period_perf = Mock(spec=PeriodPerformance)
                mock_period_perf.period_id = "cv_fold_1"
                mock_period_perf.in_sample_start = datetime(2024, 1, 1)
                mock_period_perf.in_sample_end = datetime(2024, 1, 25)
                mock_period_perf.out_of_sample_start = datetime(2024, 1, 28)
                mock_period_perf.out_of_sample_end = datetime(2024, 2, 5)
                mock_period_perf.in_sample_metrics = sample_performance_metrics
                mock_period_perf.out_of_sample_metrics = sample_performance_metrics
                mock_period_perf.trades_count_in_sample = 20
                mock_period_perf.trades_count_out_of_sample = 8
                
                mock_calc_perf.return_value = mock_period_perf
                
                result = validator.time_series_cross_validation(
                    validation_request, cv_config
                )
                
                assert result.validation_method == ValidationMethodEnum.TIME_SERIES_CV
                assert len(result.period_performances) > 0
                assert 'cv_mean_sharpe' in result.overall_metrics


class TestPerformanceCalculation:
    """Test performance calculation methods."""
    
    def test_calculate_period_performance_success(self, validator, sample_trades):
        """Test period performance calculation."""
        
        in_sample_trades = sample_trades[:30]
        out_of_sample_trades = sample_trades[30:40]
        
        # Mock strategy service
        with patch('trading_platform.services.walk_forward.out_of_sample_validator.get_strategy_service') as mock_get_service:
            mock_strategy_service = Mock()
            mock_strategy_service.backtest_period.return_value = Mock()
            mock_get_service.return_value = mock_strategy_service
            
            with patch.object(validator, '_calculate_performance_metrics') as mock_calc_metrics:
                sample_metrics = PerformanceMetrics(
                    total_trades=30, winning_trades=18, losing_trades=12,
                    win_rate=0.6, average_pnl=150.0, total_pnl=4500.0,
                    average_winner=300.0, average_loser=-125.0,
                    largest_winner=750.0, largest_loser=-300.0,
                    profit_factor=2.16, sharpe_ratio=1.25,
                    max_drawdown_pct=12.5, max_consecutive_losses=3,
                    total_commission=75.0, avg_trade_duration_minutes=32.0,
                    longest_drawdown_period_days=4, calmar_ratio=0.10
                )
                mock_calc_metrics.return_value = sample_metrics
                
                result = validator._calculate_period_performance(
                    period_id="test_period",
                    in_sample_trades=in_sample_trades,
                    out_of_sample_trades=out_of_sample_trades,
                    account_name="TEST_ACCOUNT",
                    time_bin=TimeBin.HOUR_9_MINUTE_30
                )
                
                assert isinstance(result, PeriodPerformance)
                assert result.period_id == "test_period"
                assert result.trades_count_in_sample == len(in_sample_trades)
                assert result.trades_count_out_of_sample == len(out_of_sample_trades)
                assert result.in_sample_metrics is not None
                assert result.out_of_sample_metrics is not None
    
    def test_calculate_performance_metrics_comprehensive(self, validator, sample_trades):
        """Test comprehensive performance metrics calculation."""
        
        # Test with profitable trades
        for i, trade in enumerate(sample_trades[:20]):
            trade.net_pnl = 100 + i * 10  # Increasing profits
            trade.gross_pnl = trade.net_pnl + 2.5
            trade.duration_minutes = 25 + i
        
        result = validator._calculate_performance_metrics(sample_trades[:20])
        
        assert isinstance(result, PerformanceMetrics)
        assert result.total_trades == 20
        assert result.winning_trades == 20  # All profitable
        assert result.losing_trades == 0
        assert result.win_rate == 1.0
        assert result.total_pnl > 0
        assert result.average_pnl > 0
        assert result.profit_factor > 1.0  # Since no losses
        assert result.sharpe_ratio is not None
    
    def test_calculate_performance_metrics_mixed_results(self, validator, sample_trades):
        """Test performance metrics with mixed winning/losing trades."""
        
        # Create mixed results
        for i, trade in enumerate(sample_trades[:20]):
            if i % 3 == 0:  # Every 3rd trade loses
                trade.net_pnl = -50 - i * 2
                trade.gross_pnl = trade.net_pnl + 2.5
            else:
                trade.net_pnl = 75 + i * 5
                trade.gross_pnl = trade.net_pnl + 2.5
            trade.duration_minutes = 20 + i
        
        result = validator._calculate_performance_metrics(sample_trades[:20])
        
        assert result.total_trades == 20
        assert result.winning_trades > 0
        assert result.losing_trades > 0
        assert 0 < result.win_rate < 1
        assert result.average_winner > 0
        assert result.average_loser < 0
        assert result.profit_factor > 0


class TestAnalysisAndMetrics:
    """Test analysis and metrics calculation methods."""
    
    def test_calculate_overall_metrics_comprehensive(self, validator, sample_performance_metrics):
        """Test overall metrics calculation."""
        
        # Create multiple period performances
        performances = []
        for i in range(10):
            perf = Mock(spec=PeriodPerformance)
            perf.period_id = f"period_{i}"
            perf.in_sample_metrics = sample_performance_metrics
            perf.out_of_sample_metrics = sample_performance_metrics
            perf.trades_count_in_sample = 20 + i
            perf.trades_count_out_of_sample = 8 + i//2
            performances.append(perf)
        
        config = RobustnessTestConfig(
            min_trades_threshold=10,
            performance_stability_threshold=0.3,
            overfitting_detection_threshold=0.5,
            confidence_level=0.95
        )
        
        result = validator._calculate_overall_metrics(performances, config)
        
        assert isinstance(result, dict)
        assert 'total_periods' in result
        assert 'avg_out_of_sample_sharpe' in result
        assert 'avg_out_of_sample_win_rate' in result
        assert 'overall_robustness_score' in result
        assert result['total_periods'] == 10
    
    def test_analyze_stability_comprehensive(self, validator, sample_performance_metrics):
        """Test stability analysis."""
        
        performances = []
        for i in range(8):
            perf = Mock(spec=PeriodPerformance)
            # Vary performance metrics to test stability
            oos_metrics = Mock(spec=PerformanceMetrics)
            oos_metrics.sharpe_ratio = 1.2 + np.random.uniform(-0.3, 0.3)
            oos_metrics.win_rate = 0.65 + np.random.uniform(-0.1, 0.1)
            oos_metrics.average_pnl = 120 + np.random.uniform(-20, 30)
            oos_metrics.profit_factor = 2.1 + np.random.uniform(-0.4, 0.5)
            
            perf.out_of_sample_metrics = oos_metrics
            perf.trades_count_out_of_sample = 15 + i
            performances.append(perf)
        
        result = validator._analyze_stability(performances)
        
        assert isinstance(result, dict)
        assert 'sharpe_ratio_std' in result
        assert 'sharpe_ratio_cv' in result
        assert 'win_rate_std' in result
        assert 'performance_consistency' in result
        assert 'sample_size_impact' in result
    
    def test_detect_overfitting_scenarios(self, validator):
        """Test overfitting detection with various scenarios."""
        
        config = RobustnessTestConfig(
            min_trades_threshold=10,
            performance_stability_threshold=0.3,
            overfitting_detection_threshold=0.5,
            confidence_level=0.95
        )
        
        # Scenario 1: High overfitting (large gap between IS and OOS)
        overfitted_performances = []
        for i in range(5):
            perf = Mock(spec=PeriodPerformance)
            
            # High in-sample performance
            is_metrics = Mock(spec=PerformanceMetrics)
            is_metrics.sharpe_ratio = 2.5 + i * 0.1
            is_metrics.win_rate = 0.85 + i * 0.02
            perf.in_sample_metrics = is_metrics
            
            # Poor out-of-sample performance
            oos_metrics = Mock(spec=PerformanceMetrics)
            oos_metrics.sharpe_ratio = 0.5 - i * 0.1
            oos_metrics.win_rate = 0.45 - i * 0.02
            perf.out_of_sample_metrics = oos_metrics
            
            overfitted_performances.append(perf)
        
        overfitting_result = validator._detect_overfitting(overfitted_performances, config)
        
        assert overfitting_result['avg_sharpe_gap'] > config.overfitting_detection_threshold
        assert overfitting_result['overfitting_risk_score'] > 0.5
        assert overfitting_result['periods_with_large_gaps'] > 0
        
        # Scenario 2: Good generalization (small gap between IS and OOS)
        good_performances = []
        for i in range(5):
            perf = Mock(spec=PeriodPerformance)
            
            is_metrics = Mock(spec=PerformanceMetrics)
            is_metrics.sharpe_ratio = 1.5 + i * 0.05
            is_metrics.win_rate = 0.68 + i * 0.01
            perf.in_sample_metrics = is_metrics
            
            oos_metrics = Mock(spec=PerformanceMetrics)
            oos_metrics.sharpe_ratio = 1.4 + i * 0.05  # Small gap
            oos_metrics.win_rate = 0.66 + i * 0.01
            perf.out_of_sample_metrics = oos_metrics
            
            good_performances.append(perf)
        
        good_result = validator._detect_overfitting(good_performances, config)
        
        assert good_result['avg_sharpe_gap'] < config.overfitting_detection_threshold
        assert good_result['overfitting_risk_score'] < 0.5
    
    def test_consistency_analysis(self, validator):
        """Test consistency analysis across periods."""
        
        # Create performances with varying consistency
        performances = []
        for i in range(10):
            perf = Mock(spec=PeriodPerformance)
            oos_metrics = Mock(spec=PerformanceMetrics)
            
            # Mix of positive and negative periods
            if i < 7:  # 70% positive
                oos_metrics.average_pnl = 100 + i * 20
                oos_metrics.sharpe_ratio = 1.2 + i * 0.1
                oos_metrics.win_rate = 0.62 + i * 0.02
            else:  # 30% negative
                oos_metrics.average_pnl = -50 - i * 10
                oos_metrics.sharpe_ratio = -0.3 - i * 0.1
                oos_metrics.win_rate = 0.45 - i * 0.02
            
            perf.out_of_sample_metrics = oos_metrics
            performances.append(perf)
        
        result = validator._analyze_consistency(performances)
        
        assert isinstance(result, dict)
        assert 'positive_period_ratio' in result
        assert 'good_sharpe_period_ratio' in result
        assert 'good_win_rate_period_ratio' in result
        assert 'overall_consistency_score' in result
        assert 0.6 <= result['positive_period_ratio'] <= 0.8  # Should be ~0.7


class TestRecommendationEngine:
    """Test recommendation generation."""
    
    def test_recommendation_highly_recommended(self, validator):
        """Test highly recommended scenario."""
        
        overall_metrics = {
            'overall_robustness_score': 0.85,
            'avg_out_of_sample_sharpe': 1.8,
            'performance_consistency': 0.9
        }
        
        stability_analysis = {
            'sharpe_ratio_cv': 0.15,  # Low coefficient of variation = high stability
            'performance_consistency': 0.9
        }
        
        overfitting_indicators = {
            'overfitting_risk_score': 0.2,  # Low overfitting risk
            'avg_sharpe_gap': 0.1
        }
        
        config = RobustnessTestConfig(
            min_trades_threshold=10,
            performance_stability_threshold=0.3,
            overfitting_detection_threshold=0.5,
            confidence_level=0.95
        )
        
        recommendation = validator._generate_recommendation(
            overall_metrics, stability_analysis, overfitting_indicators, config
        )
        
        assert "HIGHLY_RECOMMENDED" in recommendation
        assert "excellent robustness" in recommendation
    
    def test_recommendation_not_recommended_overfitting(self, validator):
        """Test not recommended due to overfitting."""
        
        overall_metrics = {
            'overall_robustness_score': 0.7,  # Good score
            'avg_out_of_sample_sharpe': 1.5
        }
        
        stability_analysis = {
            'sharpe_ratio_cv': 0.25,
            'performance_consistency': 0.8
        }
        
        overfitting_indicators = {
            'overfitting_risk_score': 0.85,  # High overfitting risk
            'avg_sharpe_gap': 1.2
        }
        
        config = RobustnessTestConfig(
            min_trades_threshold=10,
            performance_stability_threshold=0.3,
            overfitting_detection_threshold=0.5,
            confidence_level=0.95
        )
        
        recommendation = validator._generate_recommendation(
            overall_metrics, stability_analysis, overfitting_indicators, config
        )
        
        assert "NOT_RECOMMENDED" in recommendation
        assert "overfitting" in recommendation
    
    def test_recommendation_conditional(self, validator):
        """Test conditional recommendation."""
        
        overall_metrics = {
            'overall_robustness_score': 0.55,  # Moderate score
            'avg_out_of_sample_sharpe': 0.8
        }
        
        stability_analysis = {
            'sharpe_ratio_cv': 0.4,
            'performance_consistency': 0.6
        }
        
        overfitting_indicators = {
            'overfitting_risk_score': 0.6,  # Moderate overfitting risk
            'avg_sharpe_gap': 0.7
        }
        
        config = RobustnessTestConfig(
            min_trades_threshold=10,
            performance_stability_threshold=0.3,
            overfitting_detection_threshold=0.5,
            confidence_level=0.95
        )
        
        recommendation = validator._generate_recommendation(
            overall_metrics, stability_analysis, overfitting_indicators, config
        )
        
        assert "CONDITIONAL" in recommendation
        assert "monitor carefully" in recommendation


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""
    
    def test_validation_with_insufficient_data(self, validator, validation_request):
        """Test validation when insufficient data is available."""
        
        # Mock insufficient trades
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = []  # No trades
            
            with pytest.raises(ValueError) as exc_info:
                validator.anchored_walk_forward(validation_request)
            
            assert "Insufficient data" in str(exc_info.value)
    
    def test_validation_with_invalid_date_range(self, validator, validation_request):
        """Test validation with invalid date range."""
        
        # Set end date before start date
        validation_request.start_date = "2024-06-01"
        validation_request.end_date = "2024-01-01"
        
        with pytest.raises(ValueError) as exc_info:
            validator.anchored_walk_forward(validation_request)
        
        assert "Invalid date range" in str(exc_info.value)
    
    def test_performance_calculation_with_no_trades(self, validator):
        """Test performance calculation with empty trade list."""
        
        result = validator._calculate_performance_metrics([])
        
        assert isinstance(result, PerformanceMetrics)
        assert result.total_trades == 0
        assert result.winning_trades == 0
        assert result.losing_trades == 0
        assert result.win_rate == 0.0
        assert result.total_pnl == 0.0
    
    def test_cross_validation_with_invalid_splits(self, validator, validation_request):
        """Test cross-validation with invalid number of splits."""
        
        cv_config = CrossValidationConfig(
            n_splits=100,  # Too many splits for available data
            test_size_ratio=0.2,
            gap_days=1,
            shuffle=False
        )
        
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = []  # Insufficient trades
            
            with pytest.raises(ValueError) as exc_info:
                validator.time_series_cross_validation(validation_request, cv_config)
            
            assert "insufficient data" in str(exc_info.value).lower()


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def test_full_validation_workflow(self, validator, validation_request, sample_trades, 
                                    sample_performance_metrics):
        """Test complete validation workflow from request to result."""
        
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = sample_trades
            
            with patch.object(validator, '_calculate_performance_metrics') as mock_calc_metrics:
                mock_calc_metrics.return_value = sample_performance_metrics
                
                with patch('trading_platform.services.walk_forward.out_of_sample_validator.get_strategy_service') as mock_get_service:
                    mock_strategy_service = Mock()
                    mock_strategy_service.backtest_period.return_value = Mock()
                    mock_get_service.return_value = mock_strategy_service
                    
                    # Test each validation method
                    methods = [
                        ValidationMethodEnum.ANCHORED_WALK_FORWARD,
                        ValidationMethodEnum.ROLLING_WINDOW,
                        ValidationMethodEnum.EXPANDING_WINDOW
                    ]
                    
                    for method in methods:
                        validation_request.validation_method = method
                        
                        if method == ValidationMethodEnum.ANCHORED_WALK_FORWARD:
                            result = validator.anchored_walk_forward(validation_request)
                        elif method == ValidationMethodEnum.ROLLING_WINDOW:
                            result = validator.rolling_window_validation(validation_request)
                        elif method == ValidationMethodEnum.EXPANDING_WINDOW:
                            result = validator.expanding_window_validation(validation_request)
                        
                        # Verify complete result structure
                        assert isinstance(result, WalkForwardValidationResult)
                        assert result.validation_method == method
                        assert result.account_name == "TEST_ACCOUNT"
                        assert result.time_bin == TimeBin.HOUR_9_MINUTE_30
                        assert len(result.period_performances) > 0
                        assert result.overall_metrics is not None
                        assert result.stability_analysis is not None
                        assert result.overfitting_analysis is not None
                        assert result.consistency_analysis is not None
                        assert result.recommendation is not None
                        assert result.generation_timestamp is not None
    
    def test_comparison_across_validation_methods(self, validator, validation_request, 
                                                sample_trades, sample_performance_metrics):
        """Test comparison of results across different validation methods."""
        
        results = {}
        
        with patch.object(validator, '_get_trades_for_period') as mock_get_trades:
            mock_get_trades.return_value = sample_trades
            
            with patch.object(validator, '_calculate_performance_metrics') as mock_calc_metrics:
                mock_calc_metrics.return_value = sample_performance_metrics
                
                with patch('trading_platform.services.walk_forward.out_of_sample_validator.get_strategy_service') as mock_get_service:
                    mock_strategy_service = Mock()
                    mock_strategy_service.backtest_period.return_value = Mock()
                    mock_get_service.return_value = mock_strategy_service
                    
                    # Run all validation methods
                    validation_request.validation_method = ValidationMethodEnum.ANCHORED_WALK_FORWARD
                    results['anchored'] = validator.anchored_walk_forward(validation_request)
                    
                    validation_request.validation_method = ValidationMethodEnum.ROLLING_WINDOW
                    results['rolling'] = validator.rolling_window_validation(validation_request)
                    
                    validation_request.validation_method = ValidationMethodEnum.EXPANDING_WINDOW
                    results['expanding'] = validator.expanding_window_validation(validation_request)
                    
                    # Cross-validation
                    cv_config = CrossValidationConfig(n_splits=3, test_size_ratio=0.2)
                    results['cv'] = validator.time_series_cross_validation(validation_request, cv_config)
                    
                    # Compare results
                    for method_name, result in results.items():
                        assert isinstance(result, WalkForwardValidationResult)
                        assert result.overall_metrics is not None
                        assert 'avg_out_of_sample_sharpe' in result.overall_metrics
                        
                        # Each method should have its specific characteristics
                        if method_name == 'cv':
                            assert 'cv_mean_sharpe' in result.overall_metrics
                        
                        # All should have robustness analysis
                        assert result.stability_analysis is not None
                        assert result.overfitting_analysis is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])