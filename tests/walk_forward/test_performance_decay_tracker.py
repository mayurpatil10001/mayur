"""
Test suite for PerformanceDecayTracker - Strategy Monitoring.

Comprehensive testing of performance decay tracking methods including
prediction accuracy tracking, optimal retraining frequency analysis,
strategy degradation detection, and performance persistence testing
with synthetic degrading strategies and real performance data.

Requirements: 3.4, 3.5, 3.6
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from trading_platform.services.walk_forward.performance_decay_tracker import (
    PerformanceDecayTracker,
    PerformanceDecayConfig,
    PredictionAccuracyResult,
    RetrainingAnalysisResult,
    StrategyDegradationResult,
    PersistenceTestResult,
    DegradationAlert,
    DegradationSeverity,
    AlertType
)
from trading_platform.services.walk_forward.out_of_sample_validator import PerformanceMetrics
from trading_platform.services.time_bin_analyzer import TimeBin
from trading_platform.models.models import ProcessedTrade


class TestPerformanceDecayTracker:
    """Test suite for PerformanceDecayTracker."""
    
    @pytest.fixture
    def tracker(self):
        """Create PerformanceDecayTracker instance."""
        config = PerformanceDecayConfig(
            prediction_accuracy_window_days=30,
            retraining_analysis_lookback_days=90,
            degradation_detection_sensitivity=0.05,
            min_observations_for_analysis=10
        )
        return PerformanceDecayTracker(config)
    
    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data for testing."""
        trades = []
        base_date = datetime(2024, 1, 1, 9, 30)
        
        for i in range(50):
            trade = Mock(spec=ProcessedTrade)
            trade.trade_id = i + 1
            trade.account_name = "TEST_ACCOUNT"
            trade.entry_time = base_date + timedelta(days=i)
            trade.exit_time = base_date + timedelta(days=i, hours=1)
            trade.quantity = 100
            trade.entry_price = 100.0 + np.random.uniform(-2, 2)
            trade.exit_price = trade.entry_price + np.random.uniform(-1, 2)
            trade.gross_pnl = (trade.exit_price - trade.entry_price) * trade.quantity
            trade.net_pnl = trade.gross_pnl - 2.5
            trade.time_bin = TimeBin.HOUR_9_MINUTE_30
            trades.append(trade)
        
        return trades
    
    @pytest.fixture
    def sample_performance_metrics(self):
        """Create sample performance metrics."""
        return PerformanceMetrics(
            total_trades=30,
            winning_trades=18,
            losing_trades=12,
            win_rate=0.6,
            average_pnl=125.0,
            total_pnl=3750.0,
            average_winner=250.0,
            average_loser=-100.0,
            largest_winner=500.0,
            largest_loser=-200.0,
            profit_factor=2.25,
            sharpe_ratio=1.2,
            max_drawdown_pct=8.5,
            max_consecutive_losses=3,
            total_commission=75.0,
            avg_trade_duration_minutes=30.0,
            longest_drawdown_period_days=3,
            calmar_ratio=0.141
        )
    
    @pytest.fixture
    def degrading_performance_history(self):
        """Create degrading performance history for testing."""
        base_date = datetime(2024, 1, 1)
        history = []
        
        # Start with good performance, gradually degrade
        for i in range(20):
            date = base_date + timedelta(days=i * 5)
            
            # Gradually decreasing performance
            degradation_factor = 1.0 - (i * 0.05)
            
            metrics = PerformanceMetrics(
                total_trades=25,
                winning_trades=int(15 * degradation_factor),
                losing_trades=int(10 / degradation_factor),
                win_rate=0.6 * degradation_factor,
                average_pnl=100.0 * degradation_factor,
                total_pnl=2500.0 * degradation_factor,
                average_winner=200.0 * degradation_factor,
                average_loser=-80.0 / degradation_factor,
                largest_winner=400.0 * degradation_factor,
                largest_loser=-150.0 / degradation_factor,
                profit_factor=2.0 * degradation_factor,
                sharpe_ratio=1.5 * degradation_factor,
                max_drawdown_pct=5.0 / degradation_factor,
                max_consecutive_losses=int(2 / degradation_factor),
                total_commission=50.0,
                avg_trade_duration_minutes=25.0,
                longest_drawdown_period_days=int(2 / degradation_factor),
                calmar_ratio=0.3 * degradation_factor
            )
            
            history.append((date, metrics))
        
        return history


class TestPredictionAccuracyTracking:
    """Test prediction accuracy tracking functionality."""
    
    def test_track_prediction_accuracy_success(self, tracker, sample_trades):
        """Test successful prediction accuracy tracking."""
        
        # Create synthetic predictions
        prediction_dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(30)]
        predicted_returns = [50.0 + np.random.uniform(-20, 30) for _ in range(30)]
        
        result = tracker.track_prediction_accuracy(
            actual_trades=sample_trades[:30],
            predicted_returns=predicted_returns,
            prediction_dates=prediction_dates,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert isinstance(result, PredictionAccuracyResult)
        assert result.predictions_count == 30
        assert 0 <= result.directional_accuracy <= 1
        assert 0 <= result.hit_ratio <= 1
        assert result.mean_squared_error >= 0
        assert result.mean_absolute_error >= 0
        assert -1 <= result.correlation_coefficient <= 1
        assert len(result.actual_returns) == len(result.predicted_returns)
        assert result.period_start == min(prediction_dates)
        assert result.period_end == max(prediction_dates)
        
        # Should have confidence intervals
        assert isinstance(result.confidence_intervals, dict)
        
        # Should have statistical significance tests
        assert isinstance(result.statistical_significance, dict)
    
    def test_track_prediction_accuracy_high_correlation(self, tracker, sample_trades):
        """Test accuracy tracking with high correlation predictions."""
        
        prediction_dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(20)]
        
        # Create highly correlated predictions (actual + noise)
        actual_returns = [trade.net_pnl for trade in sample_trades[:20]]
        predicted_returns = [actual + np.random.uniform(-10, 10) for actual in actual_returns]
        
        result = tracker.track_prediction_accuracy(
            actual_trades=sample_trades[:20],
            predicted_returns=predicted_returns,
            prediction_dates=prediction_dates,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        # Should have reasonable correlation
        assert result.correlation_coefficient > 0.3
        assert result.r_squared >= 0
        assert result.directional_accuracy > 0.4
        
        # Should detect significance if correlation is strong enough
        if 'correlation_p_value' in result.statistical_significance:
            assert isinstance(result.statistical_significance['correlation_p_value'], float)
    
    def test_track_prediction_accuracy_insufficient_data(self, tracker):
        """Test accuracy tracking with insufficient data."""
        
        # Too few observations
        prediction_dates = [datetime(2024, 1, 1)]
        predicted_returns = [50.0]
        sample_trades = [Mock(spec=ProcessedTrade)]
        sample_trades[0].net_pnl = 45.0
        sample_trades[0].entry_time = datetime(2024, 1, 1, 9, 30)
        
        with pytest.raises(ValueError) as exc_info:
            tracker.track_prediction_accuracy(
                actual_trades=sample_trades,
                predicted_returns=predicted_returns,
                prediction_dates=prediction_dates,
                account_name="TEST_ACCOUNT",
                time_bin=TimeBin.HOUR_9_MINUTE_30
            )
        
        assert "Insufficient observations" in str(exc_info.value)
    
    def test_track_prediction_accuracy_mismatched_lengths(self, tracker, sample_trades):
        """Test accuracy tracking with mismatched input lengths."""
        
        prediction_dates = [datetime(2024, 1, 1), datetime(2024, 1, 2)]
        predicted_returns = [50.0]  # Different length
        
        with pytest.raises(ValueError) as exc_info:
            tracker.track_prediction_accuracy(
                actual_trades=sample_trades,
                predicted_returns=predicted_returns,
                prediction_dates=prediction_dates,
                account_name="TEST_ACCOUNT",
                time_bin=TimeBin.HOUR_9_MINUTE_30
            )
        
        assert "same length" in str(exc_info.value)
    
    def test_directional_accuracy_calculation(self, tracker, sample_trades):
        """Test directional accuracy calculation."""
        
        # Create perfect directional predictions
        prediction_dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(15)]
        actual_returns = [trade.net_pnl for trade in sample_trades[:15]]
        
        # Same sign as actual, different magnitude
        predicted_returns = [
            50.0 if actual >= 0 else -30.0 for actual in actual_returns
        ]
        
        result = tracker.track_prediction_accuracy(
            actual_trades=sample_trades[:15],
            predicted_returns=predicted_returns,
            prediction_dates=prediction_dates,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        # Should have high directional accuracy
        assert result.directional_accuracy >= 0.8


class TestRetrainingFrequencyAnalysis:
    """Test optimal retraining frequency analysis."""
    
    def test_identify_optimal_retraining_frequency_success(self, tracker, degrading_performance_history):
        """Test successful retraining frequency analysis."""
        
        # Model training dates
        training_dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 15),
            datetime(2024, 2, 1),
            datetime(2024, 2, 15)
        ]
        
        result = tracker.identify_optimal_retraining_frequency(
            performance_history=degrading_performance_history,
            model_training_dates=training_dates,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert isinstance(result, RetrainingAnalysisResult)
        assert result.current_model_age_days >= 0
        assert result.optimal_retraining_days > 0
        assert result.optimal_retraining_days <= 180  # Reasonable upper bound
        assert result.performance_decay_rate >= 0
        assert result.next_recommended_retraining > max(training_dates)
        assert -1 <= result.performance_vs_age_correlation <= 1
        assert isinstance(result.retraining_frequency_recommendation, str)
        assert len(result.stability_periods) >= 0
        assert len(result.degradation_periods) >= 0
        assert isinstance(result.historical_retraining_effectiveness, dict)
    
    def test_retraining_frequency_with_strong_decay(self, tracker):
        """Test retraining frequency with strong performance decay."""
        
        # Create performance history with strong decay after training
        base_date = datetime(2024, 1, 1)
        performance_history = []
        training_dates = [datetime(2024, 1, 1), datetime(2024, 1, 20)]
        
        for i in range(40):
            date = base_date + timedelta(days=i)
            
            # Strong decay after training
            days_since_training = (date - max([td for td in training_dates if td <= date])).days
            decay_factor = max(0.2, 1.0 - days_since_training * 0.05)
            
            metrics = PerformanceMetrics(
                total_trades=20,
                winning_trades=12,
                losing_trades=8,
                win_rate=0.6 * decay_factor,
                average_pnl=100.0 * decay_factor,
                total_pnl=2000.0 * decay_factor,
                average_winner=150.0 * decay_factor,
                average_loser=-75.0,
                largest_winner=300.0,
                largest_loser=-150.0,
                profit_factor=2.0 * decay_factor,
                sharpe_ratio=1.5 * decay_factor,
                max_drawdown_pct=8.0 / decay_factor,
                max_consecutive_losses=3,
                total_commission=40.0,
                avg_trade_duration_minutes=25.0,
                longest_drawdown_period_days=2,
                calmar_ratio=0.188 * decay_factor
            )
            
            performance_history.append((date, metrics))
        
        result = tracker.identify_optimal_retraining_frequency(
            performance_history=performance_history,
            model_training_dates=training_dates,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        # Should recommend frequent retraining due to strong decay
        assert result.performance_decay_rate > 0
        assert result.optimal_retraining_days <= 30  # Frequent retraining
        assert "week" in result.retraining_frequency_recommendation.lower() or \
               "day" in result.retraining_frequency_recommendation.lower()
    
    def test_retraining_frequency_stable_performance(self, tracker):
        """Test retraining frequency with stable performance."""
        
        # Create stable performance history
        base_date = datetime(2024, 1, 1)
        performance_history = []
        training_dates = [datetime(2024, 1, 1)]
        
        stable_metrics = PerformanceMetrics(
            total_trades=25,
            winning_trades=15,
            losing_trades=10,
            win_rate=0.6,
            average_pnl=100.0,
            total_pnl=2500.0,
            average_winner=167.0,
            average_loser=-67.0,
            largest_winner=300.0,
            largest_loser=-120.0,
            profit_factor=2.5,
            sharpe_ratio=1.3,
            max_drawdown_pct=6.0,
            max_consecutive_losses=2,
            total_commission=50.0,
            avg_trade_duration_minutes=28.0,
            longest_drawdown_period_days=2,
            calmar_ratio=0.217
        )
        
        for i in range(30):
            date = base_date + timedelta(days=i * 2)
            # Add small random variations but keep stable
            varied_metrics = PerformanceMetrics(
                total_trades=stable_metrics.total_trades,
                winning_trades=stable_metrics.winning_trades,
                losing_trades=stable_metrics.losing_trades,
                win_rate=stable_metrics.win_rate + np.random.uniform(-0.02, 0.02),
                average_pnl=stable_metrics.average_pnl + np.random.uniform(-5, 5),
                total_pnl=stable_metrics.total_pnl,
                average_winner=stable_metrics.average_winner,
                average_loser=stable_metrics.average_loser,
                largest_winner=stable_metrics.largest_winner,
                largest_loser=stable_metrics.largest_loser,
                profit_factor=stable_metrics.profit_factor,
                sharpe_ratio=stable_metrics.sharpe_ratio + np.random.uniform(-0.05, 0.05),
                max_drawdown_pct=stable_metrics.max_drawdown_pct,
                max_consecutive_losses=stable_metrics.max_consecutive_losses,
                total_commission=stable_metrics.total_commission,
                avg_trade_duration_minutes=stable_metrics.avg_trade_duration_minutes,
                longest_drawdown_period_days=stable_metrics.longest_drawdown_period_days,
                calmar_ratio=stable_metrics.calmar_ratio
            )
            performance_history.append((date, varied_metrics))
        
        result = tracker.identify_optimal_retraining_frequency(
            performance_history=performance_history,
            model_training_dates=training_dates,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        # Should recommend less frequent retraining for stable performance
        assert result.performance_decay_rate < 0.01
        assert result.optimal_retraining_days >= 30  # Less frequent
        assert "month" in result.retraining_frequency_recommendation.lower() or \
               "quarter" in result.retraining_frequency_recommendation.lower()


class TestStrategyDegradationDetection:
    """Test strategy degradation detection."""
    
    def test_detect_strategy_degradation_none(self, tracker, sample_performance_metrics):
        """Test degradation detection with no degradation."""
        
        # Create consistent performance (no degradation)
        recent_performance = [sample_performance_metrics] * 10
        historical_baseline = [sample_performance_metrics] * 20
        
        result = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert isinstance(result, StrategyDegradationResult)
        assert result.degradation_severity == DegradationSeverity.NONE
        assert result.overall_degradation_score < 0.1
        assert len(result.active_alerts) == 0
        assert result.confidence_in_degradation >= 0.1
        assert "NO SIGNIFICANT DEGRADATION" in result.recommendation
    
    def test_detect_strategy_degradation_severe(self, tracker, sample_performance_metrics):
        """Test degradation detection with severe degradation."""
        
        # Create severely degraded recent performance
        degraded_metrics = PerformanceMetrics(
            total_trades=sample_performance_metrics.total_trades,
            winning_trades=5,  # Much worse
            losing_trades=25,
            win_rate=0.2,  # Much worse
            average_pnl=-50.0,  # Negative
            total_pnl=-1500.0,
            average_winner=100.0,
            average_loser=-80.0,
            largest_winner=200.0,
            largest_loser=-200.0,
            profit_factor=0.6,  # Much worse
            sharpe_ratio=-0.5,  # Negative
            max_drawdown_pct=25.0,  # Much worse
            max_consecutive_losses=8,
            total_commission=75.0,
            avg_trade_duration_minutes=30.0,
            longest_drawdown_period_days=10,
            calmar_ratio=-0.02
        )
        
        recent_performance = [degraded_metrics] * 10
        historical_baseline = [sample_performance_metrics] * 20
        
        result = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert result.degradation_severity in [DegradationSeverity.SEVERE, DegradationSeverity.CRITICAL]
        assert result.overall_degradation_score > 0.6
        assert len(result.active_alerts) > 0
        assert result.confidence_in_degradation >= 0.5
        
        # Should have alerts for key degraded metrics
        alert_metrics = [alert.metric_name for alert in result.active_alerts]
        assert 'sharpe_ratio' in alert_metrics or 'win_rate' in alert_metrics
        
        # Should recommend immediate action
        assert "SEVERE" in result.recommendation or "CRITICAL" in result.recommendation
    
    def test_detect_strategy_degradation_moderate(self, tracker, sample_performance_metrics):
        """Test degradation detection with moderate degradation."""
        
        # Create moderately degraded performance
        moderate_degraded = PerformanceMetrics(
            total_trades=sample_performance_metrics.total_trades,
            winning_trades=12,  # Somewhat worse
            losing_trades=18,
            win_rate=0.4,  # Worse
            average_pnl=50.0,  # Worse but still positive
            total_pnl=1500.0,
            average_winner=150.0,
            average_loser=-75.0,
            largest_winner=300.0,
            largest_loser=-180.0,
            profit_factor=1.2,  # Worse
            sharpe_ratio=0.6,  # Worse
            max_drawdown_pct=15.0,  # Worse
            max_consecutive_losses=5,
            total_commission=75.0,
            avg_trade_duration_minutes=30.0,
            longest_drawdown_period_days=6,
            calmar_ratio=0.04
        )
        
        recent_performance = [moderate_degraded] * 8
        historical_baseline = [sample_performance_metrics] * 15
        
        result = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert result.degradation_severity in [DegradationSeverity.MILD, DegradationSeverity.MODERATE]
        assert 0.2 <= result.overall_degradation_score <= 0.8
        assert "MODERATE" in result.recommendation or "MILD" in result.recommendation
    
    def test_degradation_alert_generation(self, tracker, sample_performance_metrics):
        """Test degradation alert generation."""
        
        # Create performance that should trigger specific alerts
        sharpe_degraded = PerformanceMetrics(
            total_trades=sample_performance_metrics.total_trades,
            winning_trades=sample_performance_metrics.winning_trades,
            losing_trades=sample_performance_metrics.losing_trades,
            win_rate=sample_performance_metrics.win_rate,
            average_pnl=sample_performance_metrics.average_pnl,
            total_pnl=sample_performance_metrics.total_pnl,
            average_winner=sample_performance_metrics.average_winner,
            average_loser=sample_performance_metrics.average_loser,
            largest_winner=sample_performance_metrics.largest_winner,
            largest_loser=sample_performance_metrics.largest_loser,
            profit_factor=sample_performance_metrics.profit_factor,
            sharpe_ratio=0.3,  # Significantly degraded
            max_drawdown_pct=sample_performance_metrics.max_drawdown_pct,
            max_consecutive_losses=sample_performance_metrics.max_consecutive_losses,
            total_commission=sample_performance_metrics.total_commission,
            avg_trade_duration_minutes=sample_performance_metrics.avg_trade_duration_minutes,
            longest_drawdown_period_days=sample_performance_metrics.longest_drawdown_period_days,
            calmar_ratio=sample_performance_metrics.calmar_ratio
        )
        
        recent_performance = [sharpe_degraded] * 5
        historical_baseline = [sample_performance_metrics] * 10
        
        result = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        # Should generate alerts
        assert len(result.active_alerts) > 0
        
        # Check alert properties
        for alert in result.active_alerts:
            assert isinstance(alert, DegradationAlert)
            assert alert.alert_type in AlertType
            assert alert.severity in DegradationSeverity
            assert len(alert.message) > 0
            assert len(alert.recommended_action) > 0
            assert 0 <= alert.confidence_level <= 1
            assert alert.detected_at is not None


class TestPerformancePersistenceTesting:
    """Test performance persistence testing."""
    
    def test_performance_persistence_success(self, tracker, degrading_performance_history):
        """Test successful performance persistence testing."""
        
        result = tracker.test_performance_persistence(
            performance_history=degrading_performance_history,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30,
            max_lag=5
        )
        
        assert isinstance(result, PersistenceTestResult)
        assert len(result.performance_autocorrelation) <= 5
        assert 0 <= result.persistence_score <= 1
        assert 0 <= result.mean_reversion_tendency <= 1
        assert isinstance(result.streak_analysis, dict)
        assert len(result.momentum_periods) >= 0
        assert len(result.reversal_periods) >= 0
        assert isinstance(result.persistence_significance, dict)
        assert isinstance(result.predictability_metrics, dict)
        
        # Check autocorrelation structure
        for lag, correlation in result.performance_autocorrelation.items():
            assert isinstance(lag, int)
            assert lag > 0
            assert -1 <= correlation <= 1
    
    def test_persistence_with_trending_performance(self, tracker):
        """Test persistence with strongly trending performance."""
        
        # Create strongly trending (persistent) performance
        base_date = datetime(2024, 1, 1)
        trending_history = []
        
        for i in range(15):
            date = base_date + timedelta(days=i * 3)
            
            # Strong upward trend
            trend_factor = 1.0 + i * 0.1
            
            metrics = PerformanceMetrics(
                total_trades=20,
                winning_trades=12,
                losing_trades=8,
                win_rate=0.6,
                average_pnl=50.0 * trend_factor,
                total_pnl=1000.0 * trend_factor,
                average_winner=100.0 * trend_factor,
                average_loser=-50.0,
                largest_winner=200.0 * trend_factor,
                largest_loser=-100.0,
                profit_factor=2.0 * trend_factor,
                sharpe_ratio=0.8 * trend_factor,
                max_drawdown_pct=5.0,
                max_consecutive_losses=2,
                total_commission=40.0,
                avg_trade_duration_minutes=25.0,
                longest_drawdown_period_days=2,
                calmar_ratio=0.16 * trend_factor
            )
            
            trending_history.append((date, metrics))
        
        result = tracker.test_performance_persistence(
            performance_history=trending_history,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30,
            max_lag=5
        )
        
        # Should detect high persistence due to trend
        assert result.persistence_score > 0.5
        assert len(result.momentum_periods) > 0
        
        # Should have positive autocorrelations at short lags
        if 1 in result.performance_autocorrelation:
            assert result.performance_autocorrelation[1] > 0.3
    
    def test_persistence_with_mean_reverting_performance(self, tracker):
        """Test persistence with mean-reverting performance."""
        
        # Create mean-reverting performance pattern
        base_date = datetime(2024, 1, 1)
        mean_reverting_history = []
        mean_sharpe = 1.0
        
        for i in range(12):
            date = base_date + timedelta(days=i * 5)
            
            # Oscillating around mean
            if i % 2 == 0:
                sharpe = mean_sharpe + 0.5
                win_rate = 0.7
                average_pnl = 150.0
            else:
                sharpe = mean_sharpe - 0.5
                win_rate = 0.5
                average_pnl = 50.0
            
            metrics = PerformanceMetrics(
                total_trades=20,
                winning_trades=int(20 * win_rate),
                losing_trades=int(20 * (1 - win_rate)),
                win_rate=win_rate,
                average_pnl=average_pnl,
                total_pnl=average_pnl * 20,
                average_winner=200.0,
                average_loser=-100.0,
                largest_winner=400.0,
                largest_loser=-200.0,
                profit_factor=2.0,
                sharpe_ratio=sharpe,
                max_drawdown_pct=8.0,
                max_consecutive_losses=3,
                total_commission=40.0,
                avg_trade_duration_minutes=25.0,
                longest_drawdown_period_days=3,
                calmar_ratio=0.125
            )
            
            mean_reverting_history.append((date, metrics))
        
        result = tracker.test_performance_persistence(
            performance_history=mean_reverting_history,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30,
            max_lag=3
        )
        
        # Should detect mean reversion tendency
        assert result.mean_reversion_tendency > 0.3
        assert len(result.reversal_periods) > 0
        
        # Should have negative autocorrelations at some lags
        negative_autocorrs = [corr for corr in result.performance_autocorrelation.values() if corr < -0.1]
        assert len(negative_autocorrs) > 0
    
    def test_persistence_insufficient_data(self, tracker):
        """Test persistence testing with insufficient data."""
        
        # Too few observations for max_lag
        short_history = [
            (datetime(2024, 1, 1), Mock(spec=PerformanceMetrics)),
            (datetime(2024, 1, 2), Mock(spec=PerformanceMetrics))
        ]
        
        with pytest.raises(ValueError) as exc_info:
            tracker.test_performance_persistence(
                performance_history=short_history,
                account_name="TEST_ACCOUNT",
                time_bin=TimeBin.HOUR_9_MINUTE_30,
                max_lag=5
            )
        
        assert "Insufficient data" in str(exc_info.value)
    
    def test_streak_analysis(self, tracker):
        """Test performance streak analysis."""
        
        # Create performance with clear streaks
        base_date = datetime(2024, 1, 1)
        streaky_history = []
        
        # Pattern: 3 good, 2 bad, 4 good, 1 bad
        pattern = [1.5, 1.6, 1.4, 0.4, 0.3, 1.8, 1.7, 1.9, 1.6, 0.5]
        
        for i, sharpe in enumerate(pattern):
            date = base_date + timedelta(days=i * 2)
            
            metrics = PerformanceMetrics(
                total_trades=20,
                winning_trades=15 if sharpe > 1.0 else 8,
                losing_trades=5 if sharpe > 1.0 else 12,
                win_rate=0.75 if sharpe > 1.0 else 0.4,
                average_pnl=100.0 if sharpe > 1.0 else -20.0,
                total_pnl=2000.0 if sharpe > 1.0 else -400.0,
                average_winner=150.0,
                average_loser=-75.0,
                largest_winner=300.0,
                largest_loser=-150.0,
                profit_factor=3.0 if sharpe > 1.0 else 0.8,
                sharpe_ratio=sharpe,
                max_drawdown_pct=4.0 if sharpe > 1.0 else 12.0,
                max_consecutive_losses=1 if sharpe > 1.0 else 4,
                total_commission=40.0,
                avg_trade_duration_minutes=25.0,
                longest_drawdown_period_days=1 if sharpe > 1.0 else 5,
                calmar_ratio=0.25 if sharpe > 1.0 else -0.017
            )
            
            streaky_history.append((date, metrics))
        
        result = tracker.test_performance_persistence(
            performance_history=streaky_history,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30,
            max_lag=3
        )
        
        # Should detect streaks
        streak_analysis = result.streak_analysis
        assert streak_analysis['total_streaks'] > 0
        assert streak_analysis['positive_streaks_count'] > 0
        assert streak_analysis['negative_streaks_count'] > 0
        assert streak_analysis['max_positive_streak_length'] >= 3  # From our pattern
        assert 0 <= streak_analysis['streak_ratio'] <= 1


class TestConfigurationAndEdgeCases:
    """Test configuration options and edge cases."""
    
    def test_custom_configuration(self):
        """Test tracker with custom configuration."""
        
        custom_config = PerformanceDecayConfig(
            prediction_accuracy_window_days=60,
            retraining_analysis_lookback_days=180,
            degradation_detection_sensitivity=0.01,
            alert_threshold_multiplier=3.0,
            min_observations_for_analysis=30,
            significance_level=0.01,
            decay_detection_window_days=21,
            retraining_cost_factor=2.0,
            performance_weight_recent=0.8,
            enable_regime_awareness=False
        )
        
        tracker = PerformanceDecayTracker(custom_config)
        
        assert tracker.config.prediction_accuracy_window_days == 60
        assert tracker.config.degradation_detection_sensitivity == 0.01
        assert tracker.config.min_observations_for_analysis == 30
        assert tracker.config.enable_regime_awareness is False
    
    def test_default_configuration(self):
        """Test tracker with default configuration."""
        
        tracker = PerformanceDecayTracker()
        
        assert tracker.config.prediction_accuracy_window_days == 30
        assert tracker.config.retraining_analysis_lookback_days == 90
        assert tracker.config.significance_level == 0.05
        assert tracker.config.enable_regime_awareness is True
    
    def test_empty_inputs_handling(self, tracker):
        """Test handling of empty inputs."""
        
        # Empty trades
        with pytest.raises(ValueError):
            tracker.track_prediction_accuracy(
                actual_trades=[],
                predicted_returns=[1.0, 2.0],
                prediction_dates=[datetime.now()],
                account_name="TEST",
                time_bin=TimeBin.HOUR_9_MINUTE_30
            )
        
        # Empty performance history
        with pytest.raises(ValueError):
            tracker.identify_optimal_retraining_frequency(
                performance_history=[],
                model_training_dates=[datetime.now()],
                account_name="TEST",
                time_bin=TimeBin.HOUR_9_MINUTE_30
            )
        
        # Empty recent performance
        with pytest.raises(ValueError):
            tracker.detect_strategy_degradation(
                recent_performance=[],
                historical_baseline=[Mock()],
                account_name="TEST",
                time_bin=TimeBin.HOUR_9_MINUTE_30
            )
    
    def test_alert_history_tracking(self, tracker, sample_performance_metrics):
        """Test alert history tracking and deduplication."""
        
        # Create degraded performance to trigger alerts
        degraded_metrics = PerformanceMetrics(
            total_trades=sample_performance_metrics.total_trades,
            winning_trades=5,
            losing_trades=25,
            win_rate=0.17,
            average_pnl=-25.0,
            total_pnl=-750.0,
            average_winner=100.0,
            average_loser=-50.0,
            largest_winner=200.0,
            largest_loser=-150.0,
            profit_factor=0.5,
            sharpe_ratio=-0.3,
            max_drawdown_pct=20.0,
            max_consecutive_losses=6,
            total_commission=75.0,
            avg_trade_duration_minutes=30.0,
            longest_drawdown_period_days=8,
            calmar_ratio=-0.015
        )
        
        recent_performance = [degraded_metrics] * 5
        historical_baseline = [sample_performance_metrics] * 10
        
        # First detection
        result1 = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        initial_alerts = len(result1.active_alerts)
        assert initial_alerts > 0
        
        # Check alert history was updated
        assert len(tracker._alert_history) == initial_alerts
        assert len(tracker._last_alert_times) > 0
        
        # Second detection (should track frequency)
        result2 = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="TEST_ACCOUNT",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        # Should have tracked alert frequency
        for alert in result2.active_alerts:
            assert alert.alert_frequency >= 1


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def test_complete_monitoring_workflow(self, tracker):
        """Test complete monitoring workflow from prediction to degradation."""
        
        # 1. Track prediction accuracy
        prediction_dates = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(20)]
        predicted_returns = [50.0 + np.random.uniform(-25, 35) for _ in range(20)]
        
        sample_trades = []
        for i, pred_date in enumerate(prediction_dates):
            trade = Mock(spec=ProcessedTrade)
            trade.trade_id = i + 1
            trade.entry_time = pred_date.replace(hour=9, minute=30)
            trade.net_pnl = predicted_returns[i] + np.random.uniform(-15, 15)
            trade.time_bin = TimeBin.HOUR_9_MINUTE_30
            sample_trades.append(trade)
        
        accuracy_result = tracker.track_prediction_accuracy(
            actual_trades=sample_trades,
            predicted_returns=predicted_returns,
            prediction_dates=prediction_dates,
            account_name="INTEGRATION_TEST",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert isinstance(accuracy_result, PredictionAccuracyResult)
        
        # 2. Analyze retraining frequency
        performance_history = []
        base_date = datetime(2024, 1, 1)
        
        for i in range(15):
            date = base_date + timedelta(days=i * 4)
            
            metrics = PerformanceMetrics(
                total_trades=25,
                winning_trades=15,
                losing_trades=10,
                win_rate=0.6,
                average_pnl=80.0 + np.random.uniform(-20, 30),
                total_pnl=2000.0,
                average_winner=150.0,
                average_loser=-75.0,
                largest_winner=300.0,
                largest_loser=-150.0,
                profit_factor=2.0,
                sharpe_ratio=1.1 + np.random.uniform(-0.2, 0.3),
                max_drawdown_pct=7.0,
                max_consecutive_losses=3,
                total_commission=50.0,
                avg_trade_duration_minutes=28.0,
                longest_drawdown_period_days=3,
                calmar_ratio=0.157
            )
            
            performance_history.append((date, metrics))
        
        training_dates = [datetime(2024, 1, 1), datetime(2024, 1, 25)]
        
        retraining_result = tracker.identify_optimal_retraining_frequency(
            performance_history=performance_history,
            model_training_dates=training_dates,
            account_name="INTEGRATION_TEST",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert isinstance(retraining_result, RetrainingAnalysisResult)
        
        # 3. Test persistence
        persistence_result = tracker.test_performance_persistence(
            performance_history=performance_history,
            account_name="INTEGRATION_TEST",
            time_bin=TimeBin.HOUR_9_MINUTE_30,
            max_lag=4
        )
        
        assert isinstance(persistence_result, PersistenceTestResult)
        
        # 4. Test degradation detection
        recent_performance = [item[1] for item in performance_history[-5:]]
        historical_baseline = [item[1] for item in performance_history[:-5]]
        
        degradation_result = tracker.detect_strategy_degradation(
            recent_performance=recent_performance,
            historical_baseline=historical_baseline,
            account_name="INTEGRATION_TEST",
            time_bin=TimeBin.HOUR_9_MINUTE_30
        )
        
        assert isinstance(degradation_result, StrategyDegradationResult)
        
        # Verify all results are coherent
        assert accuracy_result.predictions_count > 0
        assert retraining_result.optimal_retraining_days > 0
        assert 0 <= persistence_result.persistence_score <= 1
        assert degradation_result.confidence_in_degradation > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])