"""
Performance Decay Tracker for Strategy Monitoring.

This module provides comprehensive strategy monitoring capabilities including
prediction accuracy tracking, optimal retraining frequency analysis,
strategy degradation detection, and performance persistence testing.

Requirements: 3.4, 3.5, 3.6
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import logging
from scipy import stats
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.linear_model import LinearRegression
import warnings

from ..time_bin_analyzer import TimeBin
from ...models.trading import ProcessedTrade, PerformanceMetrics


class DegradationSeverity(Enum):
    """Strategy degradation severity levels."""
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


class AlertType(Enum):
    """Performance alert types."""
    PERFORMANCE_DROP = "performance_drop"
    ACCURACY_DECLINE = "accuracy_decline"
    CONSISTENCY_LOSS = "consistency_loss"
    RETRAINING_NEEDED = "retraining_needed"
    STRATEGY_FAILURE = "strategy_failure"


@dataclass
class PredictionAccuracyResult:
    """Results from prediction accuracy tracking."""
    period_start: datetime
    period_end: datetime
    predictions_count: int
    actual_returns: List[float]
    predicted_returns: List[float]
    mean_squared_error: float
    mean_absolute_error: float
    r_squared: float
    correlation_coefficient: float
    directional_accuracy: float
    hit_ratio: float
    prediction_bias: float
    accuracy_trend: float
    confidence_intervals: Dict[str, float]
    statistical_significance: Dict[str, float]
    calculation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class RetrainingAnalysisResult:
    """Results from optimal retraining frequency analysis."""
    current_model_age_days: int
    optimal_retraining_days: int
    performance_decay_rate: float
    retraining_benefit_score: float
    cost_benefit_ratio: float
    next_recommended_retraining: datetime
    performance_vs_age_correlation: float
    decay_acceleration: float
    stability_periods: List[Tuple[datetime, datetime]]
    degradation_periods: List[Tuple[datetime, datetime]]
    retraining_frequency_recommendation: str
    historical_retraining_effectiveness: Dict[str, float]
    calculation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DegradationAlert:
    """Strategy degradation alert."""
    alert_type: AlertType
    severity: DegradationSeverity
    message: str
    metric_name: str
    current_value: float
    threshold_value: float
    confidence_level: float
    detected_at: datetime
    recommended_action: str
    time_since_last_alert: Optional[timedelta] = None
    alert_frequency: int = 1


@dataclass
class StrategyDegradationResult:
    """Results from strategy degradation detection."""
    overall_degradation_score: float
    degradation_severity: DegradationSeverity
    active_alerts: List[DegradationAlert]
    performance_trend: Dict[str, float]
    degradation_rate: float
    time_to_failure_estimate: Optional[float]
    confidence_in_degradation: float
    key_degraded_metrics: List[str]
    recent_performance_change: Dict[str, float]
    historical_context: Dict[str, Any]
    recommendation: str
    next_monitoring_interval: timedelta
    calculation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PersistenceTestResult:
    """Results from performance persistence testing."""
    test_period_start: datetime
    test_period_end: datetime
    performance_autocorrelation: Dict[int, float]  # lag -> correlation
    persistence_score: float
    mean_reversion_tendency: float
    streak_analysis: Dict[str, Any]
    momentum_periods: List[Tuple[datetime, datetime]]
    reversal_periods: List[Tuple[datetime, datetime]]
    persistence_significance: Dict[str, float]
    predictability_metrics: Dict[str, float]
    regime_persistence: Optional[Dict[str, float]]
    calculation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PerformanceDecayConfig:
    """Configuration for performance decay tracking."""
    prediction_accuracy_window_days: int = 30
    retraining_analysis_lookback_days: int = 90
    degradation_detection_sensitivity: float = 0.05
    alert_threshold_multiplier: float = 2.0
    min_observations_for_analysis: int = 20
    significance_level: float = 0.05
    decay_detection_window_days: int = 14
    retraining_cost_factor: float = 1.0
    performance_weight_recent: float = 0.7
    enable_regime_awareness: bool = True


class PerformanceDecayTracker:
    """
    Comprehensive performance decay tracking and strategy monitoring.
    
    This class provides sophisticated monitoring capabilities for trading strategies
    including prediction accuracy tracking, optimal retraining frequency analysis,
    degradation detection with statistical alerts, and performance persistence testing.
    """
    
    def __init__(self, config: Optional[PerformanceDecayConfig] = None):
        """Initialize performance decay tracker."""
        self.config = config or PerformanceDecayConfig()
        self.logger = logging.getLogger(__name__)
        
        # Alert tracking
        self._alert_history: List[DegradationAlert] = []
        self._last_alert_times: Dict[AlertType, datetime] = {}
        
        # Performance tracking
        self._performance_history: List[Tuple[datetime, PerformanceMetrics]] = []
        self._prediction_history: List[PredictionAccuracyResult] = []
        
    def track_prediction_accuracy(self, 
                                actual_trades: List[ProcessedTrade],
                                predicted_returns: List[float],
                                prediction_dates: List[datetime],
                                account_name: str,
                                time_bin: TimeBin) -> PredictionAccuracyResult:
        """
        Track prediction accuracy for forecast validation.
        
        Compares predicted returns against actual trading results to assess
        model accuracy, bias, and degradation over time.
        
        Args:
            actual_trades: List of actual trades executed
            predicted_returns: List of predicted returns from model
            prediction_dates: Dates when predictions were made
            account_name: Account name for filtering
            time_bin: Time bin for analysis
            
        Returns:
            PredictionAccuracyResult with comprehensive accuracy metrics
        """
        if not actual_trades or not predicted_returns:
            raise ValueError("Actual trades and predicted returns cannot be empty")
        
        if len(predicted_returns) != len(prediction_dates):
            raise ValueError("Predicted returns and dates must have same length")
        
        self.logger.info(f"Tracking prediction accuracy for {account_name} time-bin {time_bin}")
        
        try:
            # Align actual returns with predictions by date
            actual_returns = self._align_actual_returns_with_predictions(
                actual_trades, prediction_dates, time_bin
            )
            
            if len(actual_returns) != len(predicted_returns):
                self.logger.warning(f"Prediction alignment resulted in {len(actual_returns)} actual vs {len(predicted_returns)} predicted returns")
                min_length = min(len(actual_returns), len(predicted_returns))
                actual_returns = actual_returns[:min_length]
                predicted_returns = predicted_returns[:min_length]
                prediction_dates = prediction_dates[:min_length]
            
            if len(actual_returns) < self.config.min_observations_for_analysis:
                raise ValueError(f"Insufficient observations for analysis: {len(actual_returns)} < {self.config.min_observations_for_analysis}")
            
            # Calculate accuracy metrics
            mse = mean_squared_error(actual_returns, predicted_returns)
            mae = mean_absolute_error(actual_returns, predicted_returns)
            r2 = r2_score(actual_returns, predicted_returns)
            
            # Calculate correlation
            correlation_coeff = np.corrcoef(actual_returns, predicted_returns)[0, 1] if len(actual_returns) > 1 else 0.0
            
            # Calculate directional accuracy
            directional_accuracy = self._calculate_directional_accuracy(actual_returns, predicted_returns)
            
            # Calculate hit ratio (predictions within certain threshold)
            hit_ratio = self._calculate_hit_ratio(actual_returns, predicted_returns)
            
            # Calculate prediction bias
            prediction_bias = np.mean(np.array(predicted_returns) - np.array(actual_returns))
            
            # Calculate accuracy trend
            accuracy_trend = self._calculate_accuracy_trend(actual_returns, predicted_returns, prediction_dates)
            
            # Calculate confidence intervals
            confidence_intervals = self._calculate_prediction_confidence_intervals(
                actual_returns, predicted_returns
            )
            
            # Statistical significance testing
            statistical_significance = self._test_prediction_significance(
                actual_returns, predicted_returns
            )
            
            result = PredictionAccuracyResult(
                period_start=min(prediction_dates),
                period_end=max(prediction_dates),
                predictions_count=len(predicted_returns),
                actual_returns=actual_returns,
                predicted_returns=predicted_returns,
                mean_squared_error=mse,
                mean_absolute_error=mae,
                r_squared=r2,
                correlation_coefficient=correlation_coeff,
                directional_accuracy=directional_accuracy,
                hit_ratio=hit_ratio,
                prediction_bias=prediction_bias,
                accuracy_trend=accuracy_trend,
                confidence_intervals=confidence_intervals,
                statistical_significance=statistical_significance
            )
            
            # Store for historical tracking
            self._prediction_history.append(result)
            
            self.logger.info(f"Prediction accuracy tracking completed: R²={r2:.3f}, Correlation={correlation_coeff:.3f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in prediction accuracy tracking: {e}")
            raise
    
    def identify_optimal_retraining_frequency(self,
                                            performance_history: List[Tuple[datetime, PerformanceMetrics]],
                                            model_training_dates: List[datetime],
                                            account_name: str,
                                            time_bin: TimeBin) -> RetrainingAnalysisResult:
        """
        Identify optimal retraining frequency through performance analysis.
        
        Analyzes the relationship between model age and performance to determine
        the optimal frequency for model retraining.
        
        Args:
            performance_history: Historical performance metrics with timestamps
            model_training_dates: Dates when model was retrained
            account_name: Account name for analysis
            time_bin: Time bin for analysis
            
        Returns:
            RetrainingAnalysisResult with optimal frequency recommendations
        """
        if not performance_history or not model_training_dates:
            raise ValueError("Performance history and training dates cannot be empty")
        
        self.logger.info(f"Analyzing optimal retraining frequency for {account_name} time-bin {time_bin}")
        
        try:
            # Calculate current model age
            current_model_age = (datetime.now() - max(model_training_dates)).days
            
            # Analyze performance vs model age relationship
            performance_decay_analysis = self._analyze_performance_vs_age(
                performance_history, model_training_dates
            )
            
            # Calculate decay rate
            decay_rate = performance_decay_analysis['decay_rate']
            
            # Estimate retraining benefit
            retraining_benefit = self._estimate_retraining_benefit(
                performance_history, model_training_dates
            )
            
            # Calculate cost-benefit ratio
            cost_benefit_ratio = self._calculate_retraining_cost_benefit(
                retraining_benefit, self.config.retraining_cost_factor
            )
            
            # Determine optimal retraining frequency
            optimal_days = self._determine_optimal_retraining_days(
                performance_decay_analysis, cost_benefit_ratio
            )
            
            # Calculate next recommended retraining date
            next_retraining = max(model_training_dates) + timedelta(days=optimal_days)
            
            # Analyze stability and degradation periods
            stability_periods, degradation_periods = self._identify_performance_periods(
                performance_history
            )
            
            # Generate recommendation
            frequency_recommendation = self._generate_retraining_recommendation(
                optimal_days, decay_rate, retraining_benefit
            )
            
            # Historical effectiveness analysis
            historical_effectiveness = self._analyze_historical_retraining_effectiveness(
                performance_history, model_training_dates
            )
            
            result = RetrainingAnalysisResult(
                current_model_age_days=current_model_age,
                optimal_retraining_days=optimal_days,
                performance_decay_rate=decay_rate,
                retraining_benefit_score=retraining_benefit,
                cost_benefit_ratio=cost_benefit_ratio,
                next_recommended_retraining=next_retraining,
                performance_vs_age_correlation=performance_decay_analysis['correlation'],
                decay_acceleration=performance_decay_analysis['acceleration'],
                stability_periods=stability_periods,
                degradation_periods=degradation_periods,
                retraining_frequency_recommendation=frequency_recommendation,
                historical_retraining_effectiveness=historical_effectiveness
            )
            
            self.logger.info(f"Optimal retraining analysis completed: {optimal_days} days recommended")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in retraining frequency analysis: {e}")
            raise
    
    def detect_strategy_degradation(self,
                                  recent_performance: List[PerformanceMetrics],
                                  historical_baseline: List[PerformanceMetrics],
                                  account_name: str,
                                  time_bin: TimeBin) -> StrategyDegradationResult:
        """
        Detect strategy degradation with statistical alerts.
        
        Compares recent performance against historical baseline to detect
        significant degradation and generate appropriate alerts.
        
        Args:
            recent_performance: Recent performance metrics
            historical_baseline: Historical baseline performance
            account_name: Account name for analysis
            time_bin: Time bin for analysis
            
        Returns:
            StrategyDegradationResult with degradation assessment and alerts
        """
        if not recent_performance or not historical_baseline:
            raise ValueError("Recent performance and historical baseline cannot be empty")
        
        self.logger.info(f"Detecting strategy degradation for {account_name} time-bin {time_bin}")
        
        try:
            # Calculate degradation scores for key metrics
            degradation_scores = self._calculate_degradation_scores(
                recent_performance, historical_baseline
            )
            
            # Determine overall degradation severity
            overall_score = np.mean(list(degradation_scores.values()))
            severity = self._classify_degradation_severity(overall_score)
            
            # Generate alerts for significant degradations
            alerts = self._generate_degradation_alerts(
                degradation_scores, recent_performance, historical_baseline
            )
            
            # Calculate performance trends
            performance_trends = self._calculate_performance_trends(recent_performance)
            
            # Estimate time to failure
            time_to_failure = self._estimate_time_to_failure(
                performance_trends, degradation_scores
            )
            
            # Calculate confidence in degradation detection
            confidence = self._calculate_degradation_confidence(
                degradation_scores, len(recent_performance), len(historical_baseline)
            )
            
            # Identify key degraded metrics
            key_degraded_metrics = self._identify_key_degraded_metrics(degradation_scores)
            
            # Analyze recent performance changes
            recent_changes = self._analyze_recent_performance_changes(recent_performance)
            
            # Build historical context
            historical_context = self._build_historical_context(
                historical_baseline, degradation_scores
            )
            
            # Generate recommendation
            recommendation = self._generate_degradation_recommendation(
                severity, alerts, key_degraded_metrics
            )
            
            # Determine next monitoring interval
            next_interval = self._determine_monitoring_interval(severity, confidence)
            
            result = StrategyDegradationResult(
                overall_degradation_score=overall_score,
                degradation_severity=severity,
                active_alerts=alerts,
                performance_trend=performance_trends,
                degradation_rate=self._calculate_degradation_rate(degradation_scores),
                time_to_failure_estimate=time_to_failure,
                confidence_in_degradation=confidence,
                key_degraded_metrics=key_degraded_metrics,
                recent_performance_change=recent_changes,
                historical_context=historical_context,
                recommendation=recommendation,
                next_monitoring_interval=next_interval
            )
            
            # Update alert history
            self._alert_history.extend(alerts)
            for alert in alerts:
                self._last_alert_times[alert.alert_type] = alert.detected_at
            
            self.logger.info(f"Degradation detection completed: {severity.value} severity with {len(alerts)} alerts")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in strategy degradation detection: {e}")
            raise
    
    def test_performance_persistence(self,
                                   performance_history: List[Tuple[datetime, PerformanceMetrics]],
                                   account_name: str,
                                   time_bin: TimeBin,
                                   max_lag: int = 10) -> PersistenceTestResult:
        """
        Test performance persistence across time periods.
        
        Analyzes autocorrelation in performance metrics to determine if
        performance tends to persist or mean-revert over time.
        
        Args:
            performance_history: Historical performance with timestamps
            account_name: Account name for analysis
            time_bin: Time bin for analysis
            max_lag: Maximum lag for autocorrelation analysis
            
        Returns:
            PersistenceTestResult with persistence analysis
        """
        if not performance_history:
            raise ValueError("Performance history cannot be empty")
        
        if len(performance_history) < max_lag + 1:
            raise ValueError(f"Insufficient data for persistence testing: need at least {max_lag + 1} observations")
        
        self.logger.info(f"Testing performance persistence for {account_name} time-bin {time_bin}")
        
        try:
            # Extract performance series
            dates = [item[0] for item in performance_history]
            performance_metrics = [item[1] for item in performance_history]
            
            # Calculate autocorrelations for different metrics
            autocorrelations = self._calculate_autocorrelations(
                performance_metrics, max_lag
            )
            
            # Calculate overall persistence score
            persistence_score = self._calculate_persistence_score(autocorrelations)
            
            # Test for mean reversion tendency
            mean_reversion_tendency = self._test_mean_reversion_tendency(performance_metrics)
            
            # Analyze performance streaks
            streak_analysis = self._analyze_performance_streaks(performance_metrics)
            
            # Identify momentum and reversal periods
            momentum_periods, reversal_periods = self._identify_momentum_reversal_periods(
                dates, performance_metrics
            )
            
            # Statistical significance testing
            persistence_significance = self._test_persistence_significance(
                autocorrelations, len(performance_metrics)
            )
            
            # Calculate predictability metrics
            predictability_metrics = self._calculate_predictability_metrics(
                performance_metrics, autocorrelations
            )
            
            # Regime-specific persistence (if regime data available)
            regime_persistence = self._analyze_regime_specific_persistence(
                dates, performance_metrics
            ) if self.config.enable_regime_awareness else None
            
            result = PersistenceTestResult(
                test_period_start=min(dates),
                test_period_end=max(dates),
                performance_autocorrelation=autocorrelations,
                persistence_score=persistence_score,
                mean_reversion_tendency=mean_reversion_tendency,
                streak_analysis=streak_analysis,
                momentum_periods=momentum_periods,
                reversal_periods=reversal_periods,
                persistence_significance=persistence_significance,
                predictability_metrics=predictability_metrics,
                regime_persistence=regime_persistence
            )
            
            self.logger.info(f"Persistence testing completed: persistence score = {persistence_score:.3f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in performance persistence testing: {e}")
            raise
    
    # Helper methods for prediction accuracy tracking
    
    def _align_actual_returns_with_predictions(self, 
                                             actual_trades: List[ProcessedTrade],
                                             prediction_dates: List[datetime],
                                             time_bin: TimeBin) -> List[float]:
        """Align actual trade returns with prediction dates."""
        # Group trades by date and time bin
        daily_returns = {}
        
        for trade in actual_trades:
            trade_date = trade.entry_time.date()
            trade_time_bin = TimeBin.from_time(trade.entry_time.hour, trade.entry_time.minute)
            
            if trade_time_bin == time_bin:
                if trade_date not in daily_returns:
                    daily_returns[trade_date] = []
                daily_returns[trade_date].append(trade.net_pnl)
        
        # Calculate daily aggregated returns
        aligned_returns = []
        for pred_date in prediction_dates:
            pred_date_key = pred_date.date()
            if pred_date_key in daily_returns:
                daily_return = sum(daily_returns[pred_date_key])
                aligned_returns.append(daily_return)
            else:
                # No trades on this date, assume zero return
                aligned_returns.append(0.0)
        
        return aligned_returns
    
    def _calculate_directional_accuracy(self, actual: List[float], predicted: List[float]) -> float:
        """Calculate directional accuracy (same sign)."""
        if not actual or not predicted or len(actual) != len(predicted):
            return 0.0
        
        correct_directions = sum(
            1 for a, p in zip(actual, predicted)
            if (a >= 0 and p >= 0) or (a < 0 and p < 0)
        )
        
        return correct_directions / len(actual)
    
    def _calculate_hit_ratio(self, actual: List[float], predicted: List[float], 
                           threshold_pct: float = 0.1) -> float:
        """Calculate hit ratio (predictions within threshold of actual)."""
        if not actual or not predicted or len(actual) != len(predicted):
            return 0.0
        
        hits = 0
        for a, p in zip(actual, predicted):
            if a == 0:
                threshold = threshold_pct * 100  # Absolute threshold for zero returns
            else:
                threshold = abs(a) * threshold_pct
            
            if abs(a - p) <= threshold:
                hits += 1
        
        return hits / len(actual)
    
    def _calculate_accuracy_trend(self, actual: List[float], predicted: List[float],
                                dates: List[datetime]) -> float:
        """Calculate trend in prediction accuracy over time."""
        if len(actual) < 3:
            return 0.0
        
        # Calculate rolling accuracy (R-squared over windows)
        window_size = min(10, len(actual) // 3)
        rolling_accuracies = []
        
        for i in range(window_size, len(actual)):
            window_actual = actual[i-window_size:i]
            window_predicted = predicted[i-window_size:i]
            
            try:
                r2 = r2_score(window_actual, window_predicted)
                rolling_accuracies.append(r2)
            except:
                rolling_accuracies.append(0.0)
        
        if len(rolling_accuracies) < 2:
            return 0.0
        
        # Calculate trend slope
        x = np.arange(len(rolling_accuracies))
        try:
            slope, _, _, _, _ = stats.linregress(x, rolling_accuracies)
            return float(slope)
        except:
            return 0.0
    
    def _calculate_prediction_confidence_intervals(self, actual: List[float], 
                                                 predicted: List[float]) -> Dict[str, float]:
        """Calculate confidence intervals for prediction metrics."""
        if len(actual) < 3:
            return {}
        
        try:
            # Bootstrap confidence intervals
            n_bootstrap = 1000
            bootstrap_r2 = []
            bootstrap_corr = []
            
            for _ in range(n_bootstrap):
                indices = np.random.choice(len(actual), size=len(actual), replace=True)
                boot_actual = [actual[i] for i in indices]
                boot_predicted = [predicted[i] for i in indices]
                
                try:
                    boot_r2 = r2_score(boot_actual, boot_predicted)
                    boot_corr = np.corrcoef(boot_actual, boot_predicted)[0, 1]
                    
                    bootstrap_r2.append(boot_r2)
                    bootstrap_corr.append(boot_corr)
                except:
                    continue
            
            confidence_intervals = {}
            if bootstrap_r2:
                confidence_intervals['r2_95_lower'] = np.percentile(bootstrap_r2, 2.5)
                confidence_intervals['r2_95_upper'] = np.percentile(bootstrap_r2, 97.5)
            
            if bootstrap_corr:
                confidence_intervals['corr_95_lower'] = np.percentile(bootstrap_corr, 2.5)
                confidence_intervals['corr_95_upper'] = np.percentile(bootstrap_corr, 97.5)
            
            return confidence_intervals
            
        except Exception as e:
            self.logger.warning(f"Error calculating confidence intervals: {e}")
            return {}
    
    def _test_prediction_significance(self, actual: List[float], 
                                    predicted: List[float]) -> Dict[str, float]:
        """Test statistical significance of predictions."""
        if len(actual) < 3:
            return {}
        
        try:
            significance_tests = {}
            
            # Correlation significance test
            correlation_coeff = np.corrcoef(actual, predicted)[0, 1]
            if not np.isnan(correlation_coeff):
                # t-test for correlation significance
                t_stat = correlation_coeff * np.sqrt((len(actual) - 2) / (1 - correlation_coeff**2))
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), len(actual) - 2))
                significance_tests['correlation_p_value'] = p_value
                significance_tests['correlation_significant'] = p_value < self.config.significance_level
            
            # Test if predictions are better than random (zero correlation)
            if len(actual) > 10:
                # Permutation test
                n_permutations = 1000
                perm_correlations = []
                
                for _ in range(n_permutations):
                    perm_predicted = np.random.permutation(predicted)
                    perm_corr = np.corrcoef(actual, perm_predicted)[0, 1]
                    if not np.isnan(perm_corr):
                        perm_correlations.append(perm_corr)
                
                if perm_correlations:
                    observed_corr = correlation_coeff
                    p_value_perm = sum(1 for pc in perm_correlations if abs(pc) >= abs(observed_corr)) / len(perm_correlations)
                    significance_tests['permutation_p_value'] = p_value_perm
                    significance_tests['better_than_random'] = p_value_perm < self.config.significance_level
            
            return significance_tests
            
        except Exception as e:
            self.logger.warning(f"Error in significance testing: {e}")
            return {}
    
    # Helper methods for retraining frequency analysis
    
    def _analyze_performance_vs_age(self, 
                                  performance_history: List[Tuple[datetime, PerformanceMetrics]],
                                  training_dates: List[datetime]) -> Dict[str, float]:
        """Analyze relationship between model age and performance."""
        
        # Calculate model age for each performance measurement
        ages = []
        sharpe_ratios = []
        
        for perf_date, metrics in performance_history:
            # Find the most recent training date before this performance measurement
            relevant_training_dates = [td for td in training_dates if td <= perf_date]
            if relevant_training_dates:
                last_training = max(relevant_training_dates)
                age_days = (perf_date - last_training).days
                ages.append(age_days)
                sharpe_ratios.append(metrics.sharpe_ratio or 0.0)
        
        if len(ages) < 3:
            return {'decay_rate': 0.0, 'correlation': 0.0, 'acceleration': 0.0}
        
        # Calculate correlation between age and performance
        correlation = np.corrcoef(ages, sharpe_ratios)[0, 1] if len(ages) > 1 else 0.0
        
        # Calculate decay rate (slope)
        try:
            slope, _, _, _, _ = stats.linregress(ages, sharpe_ratios)
            decay_rate = abs(slope)  # Make positive for decay rate
        except:
            decay_rate = 0.0
        
        # Calculate acceleration (second derivative approximation)
        acceleration = 0.0
        if len(ages) >= 5:
            try:
                # Fit quadratic to detect acceleration
                ages_array = np.array(ages)
                sharpe_array = np.array(sharpe_ratios)
                coeffs = np.polyfit(ages_array, sharpe_array, 2)
                acceleration = abs(2 * coeffs[0])  # Second derivative
            except:
                acceleration = 0.0
        
        return {
            'decay_rate': decay_rate,
            'correlation': correlation,
            'acceleration': acceleration
        }
    
    def _estimate_retraining_benefit(self,
                                   performance_history: List[Tuple[datetime, PerformanceMetrics]],
                                   training_dates: List[datetime]) -> float:
        """Estimate benefit gained from retraining."""
        
        if len(training_dates) < 2:
            return 0.0
        
        # Look at performance before and after each retraining
        retraining_improvements = []
        
        for i in range(1, len(training_dates)):
            prev_training = training_dates[i-1]
            curr_training = training_dates[i]
            
            # Get performance just before retraining
            before_perfs = [
                metrics for date, metrics in performance_history
                if prev_training < date < curr_training
            ]
            
            # Get performance just after retraining
            after_perfs = [
                metrics for date, metrics in performance_history
                if curr_training < date < curr_training + timedelta(days=30)
            ]
            
            if before_perfs and after_perfs:
                before_avg = np.mean([m.sharpe_ratio or 0.0 for m in before_perfs])
                after_avg = np.mean([m.sharpe_ratio or 0.0 for m in after_perfs])
                improvement = after_avg - before_avg
                retraining_improvements.append(improvement)
        
        if retraining_improvements:
            return float(np.mean(retraining_improvements))
        else:
            return 0.0
    
    def _calculate_retraining_cost_benefit(self, benefit: float, cost_factor: float) -> float:
        """Calculate cost-benefit ratio for retraining."""
        if cost_factor <= 0:
            return float('inf') if benefit > 0 else 0.0
        
        return benefit / cost_factor
    
    def _determine_optimal_retraining_days(self, 
                                         decay_analysis: Dict[str, float],
                                         cost_benefit_ratio: float) -> int:
        """Determine optimal retraining frequency in days."""
        
        decay_rate = decay_analysis['decay_rate']
        
        if decay_rate <= 0:
            # No decay detected, recommend longer intervals
            return 90
        
        # Calculate when performance would degrade significantly
        significant_degradation_threshold = 0.1  # 10% performance drop
        days_to_degradation = significant_degradation_threshold / decay_rate
        
        # Consider cost-benefit ratio
        if cost_benefit_ratio > 2.0:
            # High benefit, retrain more frequently
            optimal_days = max(7, int(days_to_degradation * 0.5))
        elif cost_benefit_ratio > 1.0:
            # Moderate benefit, retrain at degradation point
            optimal_days = max(14, int(days_to_degradation * 0.7))
        else:
            # Low benefit, retrain less frequently
            optimal_days = max(30, int(days_to_degradation * 1.2))
        
        # Cap at reasonable limits
        return min(180, max(7, optimal_days))
    
    def _identify_performance_periods(self, 
                                    performance_history: List[Tuple[datetime, PerformanceMetrics]]
                                    ) -> Tuple[List[Tuple[datetime, datetime]], List[Tuple[datetime, datetime]]]:
        """Identify periods of stability and degradation."""
        
        if len(performance_history) < 5:
            return [], []
        
        dates = [item[0] for item in performance_history]
        sharpe_ratios = [item[1].sharpe_ratio or 0.0 for item in performance_history]
        
        # Calculate rolling mean and std
        window = min(10, len(sharpe_ratios) // 3)
        rolling_mean = pd.Series(sharpe_ratios).rolling(window=window).mean()
        rolling_std = pd.Series(sharpe_ratios).rolling(window=window).std()
        
        stability_periods = []
        degradation_periods = []
        
        # Identify periods based on volatility and trend
        in_stable_period = False
        in_degradation_period = False
        period_start = None
        
        for i in range(window, len(sharpe_ratios)):
            is_stable = rolling_std.iloc[i] < 0.2  # Low volatility
            is_degrading = (
                i > window and 
                rolling_mean.iloc[i] < rolling_mean.iloc[i-5] - 0.1  # Declining trend
            )
            
            # Stability period logic
            if is_stable and not in_stable_period:
                period_start = dates[i]
                in_stable_period = True
            elif not is_stable and in_stable_period:
                stability_periods.append((period_start, dates[i]))
                in_stable_period = False
            
            # Degradation period logic
            if is_degrading and not in_degradation_period:
                period_start = dates[i]
                in_degradation_period = True
            elif not is_degrading and in_degradation_period:
                degradation_periods.append((period_start, dates[i]))
                in_degradation_period = False
        
        # Close any open periods
        if in_stable_period and period_start:
            stability_periods.append((period_start, dates[-1]))
        if in_degradation_period and period_start:
            degradation_periods.append((period_start, dates[-1]))
        
        return stability_periods, degradation_periods
    
    def _generate_retraining_recommendation(self, 
                                          optimal_days: int,
                                          decay_rate: float,
                                          benefit_score: float) -> str:
        """Generate human-readable retraining recommendation."""
        
        if optimal_days <= 14:
            frequency = "weekly"
        elif optimal_days <= 30:
            frequency = "bi-weekly"
        elif optimal_days <= 60:
            frequency = "monthly"
        else:
            frequency = "quarterly"
        
        if benefit_score > 0.2:
            urgency = "high"
        elif benefit_score > 0.1:
            urgency = "moderate"
        else:
            urgency = "low"
        
        if decay_rate > 0.01:
            decay_desc = "significant"
        elif decay_rate > 0.005:
            decay_desc = "moderate"
        else:
            decay_desc = "minimal"
        
        recommendation = (
            f"Recommend {frequency} retraining (every {optimal_days} days) "
            f"with {urgency} priority. Performance decay is {decay_desc} "
            f"(rate: {decay_rate:.4f} per day). Expected benefit from "
            f"retraining: {benefit_score:.3f} Sharpe ratio improvement."
        )
        
        return recommendation
    
    def _analyze_historical_retraining_effectiveness(self,
                                                   performance_history: List[Tuple[datetime, PerformanceMetrics]],
                                                   training_dates: List[datetime]) -> Dict[str, float]:
        """Analyze historical effectiveness of retraining."""
        
        if len(training_dates) < 2:
            return {}
        
        effectiveness_metrics = {}
        
        # Calculate average improvement after retraining
        improvements = []
        for i in range(1, len(training_dates)):
            training_date = training_dates[i]
            
            # Performance 30 days before and after retraining
            before_perfs = [
                metrics.sharpe_ratio or 0.0 for date, metrics in performance_history
                if training_date - timedelta(days=30) <= date < training_date
            ]
            
            after_perfs = [
                metrics.sharpe_ratio or 0.0 for date, metrics in performance_history
                if training_date < date <= training_date + timedelta(days=30)
            ]
            
            if before_perfs and after_perfs:
                improvement = np.mean(after_perfs) - np.mean(before_perfs)
                improvements.append(improvement)
        
        if improvements:
            effectiveness_metrics['avg_improvement'] = float(np.mean(improvements))
            effectiveness_metrics['improvement_consistency'] = float(np.std(improvements))
            effectiveness_metrics['positive_improvement_ratio'] = float(sum(1 for imp in improvements if imp > 0) / len(improvements))
        
        return effectiveness_metrics
    
    # Helper methods for degradation detection
    
    def _calculate_degradation_scores(self,
                                    recent_performance: List[PerformanceMetrics],
                                    historical_baseline: List[PerformanceMetrics]) -> Dict[str, float]:
        """Calculate degradation scores for key performance metrics."""
        
        degradation_scores = {}
        
        # Key metrics to monitor for degradation
        metrics_to_check = [
            ('sharpe_ratio', lambda m: m.sharpe_ratio or 0.0),
            ('win_rate', lambda m: m.win_rate),
            ('profit_factor', lambda m: m.profit_factor or 0.0),
            ('average_pnl', lambda m: m.average_pnl),
            ('max_drawdown_pct', lambda m: m.max_drawdown_pct or 0.0)  # Lower is better
        ]
        
        for metric_name, extractor in metrics_to_check:
            try:
                recent_values = [extractor(m) for m in recent_performance if extractor(m) is not None]
                historical_values = [extractor(m) for m in historical_baseline if extractor(m) is not None]
                
                if not recent_values or not historical_values:
                    continue
                
                recent_mean = np.mean(recent_values)
                historical_mean = np.mean(historical_values)
                historical_std = np.std(historical_values)
                
                if historical_std > 0:
                    # Z-score based degradation
                    if metric_name == 'max_drawdown_pct':
                        # For drawdown, lower is better, so flip the sign
                        z_score = (historical_mean - recent_mean) / historical_std
                    else:
                        z_score = (historical_mean - recent_mean) / historical_std
                    
                    # Convert to degradation score (0-1, where 1 is maximum degradation)
                    degradation_score = max(0.0, min(1.0, z_score / 3.0))  # 3-sigma normalization
                else:
                    # If no historical variation, use percentage change
                    if historical_mean != 0:
                        pct_change = (recent_mean - historical_mean) / abs(historical_mean)
                        if metric_name == 'max_drawdown_pct':
                            pct_change = -pct_change  # Flip for drawdown
                        degradation_score = max(0.0, min(1.0, -pct_change))
                    else:
                        degradation_score = 0.0
                
                degradation_scores[metric_name] = degradation_score
                
            except Exception as e:
                self.logger.warning(f"Error calculating degradation for {metric_name}: {e}")
                degradation_scores[metric_name] = 0.0
        
        return degradation_scores
    
    def _classify_degradation_severity(self, overall_score: float) -> DegradationSeverity:
        """Classify degradation severity based on overall score."""
        
        if overall_score < 0.1:
            return DegradationSeverity.NONE
        elif overall_score < 0.3:
            return DegradationSeverity.MILD
        elif overall_score < 0.6:
            return DegradationSeverity.MODERATE
        elif overall_score < 0.8:
            return DegradationSeverity.SEVERE
        else:
            return DegradationSeverity.CRITICAL
    
    def _generate_degradation_alerts(self,
                                   degradation_scores: Dict[str, float],
                                   recent_performance: List[PerformanceMetrics],
                                   historical_baseline: List[PerformanceMetrics]) -> List[DegradationAlert]:
        """Generate alerts for significant degradations."""
        
        alerts = []
        current_time = datetime.now()
        
        # Define alert thresholds
        alert_thresholds = {
            'sharpe_ratio': (0.3, AlertType.PERFORMANCE_DROP),
            'win_rate': (0.3, AlertType.PERFORMANCE_DROP),
            'profit_factor': (0.4, AlertType.PERFORMANCE_DROP),
            'average_pnl': (0.3, AlertType.PERFORMANCE_DROP),
            'max_drawdown_pct': (0.5, AlertType.PERFORMANCE_DROP)
        }
        
        for metric_name, degradation_score in degradation_scores.items():
            if metric_name in alert_thresholds:
                threshold, alert_type = alert_thresholds[metric_name]
                
                if degradation_score >= threshold:
                    # Calculate current and historical values for context
                    recent_values = self._extract_metric_values(recent_performance, metric_name)
                    historical_values = self._extract_metric_values(historical_baseline, metric_name)
                    
                    current_value = np.mean(recent_values) if recent_values else 0.0
                    historical_value = np.mean(historical_values) if historical_values else 0.0
                    
                    # Determine severity
                    if degradation_score >= 0.8:
                        severity = DegradationSeverity.CRITICAL
                    elif degradation_score >= 0.6:
                        severity = DegradationSeverity.SEVERE
                    elif degradation_score >= 0.3:
                        severity = DegradationSeverity.MODERATE
                    else:
                        severity = DegradationSeverity.MILD
                    
                    # Generate alert message
                    message = self._generate_alert_message(
                        metric_name, current_value, historical_value, degradation_score
                    )
                    
                    # Calculate confidence level
                    confidence = min(0.99, degradation_score + 0.5)
                    
                    # Generate recommendation
                    recommendation = self._generate_alert_recommendation(
                        metric_name, severity, degradation_score
                    )
                    
                    # Check for recent similar alerts to avoid spam
                    time_since_last = None
                    if alert_type in self._last_alert_times:
                        time_since_last = current_time - self._last_alert_times[alert_type]
                    
                    alert_frequency = len([
                        a for a in self._alert_history
                        if a.alert_type == alert_type and
                        a.detected_at > current_time - timedelta(days=7)
                    ]) + 1
                    
                    alert = DegradationAlert(
                        alert_type=alert_type,
                        severity=severity,
                        message=message,
                        metric_name=metric_name,
                        current_value=current_value,
                        threshold_value=historical_value,
                        confidence_level=confidence,
                        detected_at=current_time,
                        recommended_action=recommendation,
                        time_since_last_alert=time_since_last,
                        alert_frequency=alert_frequency
                    )
                    
                    alerts.append(alert)
        
        return alerts
    
    def _extract_metric_values(self, performance_list: List[PerformanceMetrics], 
                             metric_name: str) -> List[float]:
        """Extract metric values from performance list."""
        
        extractors = {
            'sharpe_ratio': lambda m: m.sharpe_ratio or 0.0,
            'win_rate': lambda m: m.win_rate,
            'profit_factor': lambda m: m.profit_factor or 0.0,
            'average_pnl': lambda m: m.average_pnl,
            'max_drawdown_pct': lambda m: m.max_drawdown_pct or 0.0
        }
        
        if metric_name not in extractors:
            return []
        
        extractor = extractors[metric_name]
        return [extractor(m) for m in performance_list if extractor(m) is not None]
    
    def _generate_alert_message(self, metric_name: str, current_value: float,
                              historical_value: float, degradation_score: float) -> str:
        """Generate human-readable alert message."""
        
        metric_display_names = {
            'sharpe_ratio': 'Sharpe Ratio',
            'win_rate': 'Win Rate',
            'profit_factor': 'Profit Factor',
            'average_pnl': 'Average P&L',
            'max_drawdown_pct': 'Maximum Drawdown'
        }
        
        display_name = metric_display_names.get(metric_name, metric_name)
        
        if metric_name == 'win_rate':
            current_display = f"{current_value:.1%}"
            historical_display = f"{historical_value:.1%}"
        elif metric_name in ['max_drawdown_pct']:
            current_display = f"{current_value:.1f}%"
            historical_display = f"{historical_value:.1f}%"
        elif metric_name == 'average_pnl':
            current_display = f"${current_value:.2f}"
            historical_display = f"${historical_value:.2f}"
        else:
            current_display = f"{current_value:.3f}"
            historical_display = f"{historical_value:.3f}"
        
        change_direction = "increased" if current_value > historical_value else "decreased"
        if metric_name == 'max_drawdown_pct':
            change_direction = "increased" if current_value > historical_value else "improved"
        
        message = (
            f"{display_name} has {change_direction} significantly. "
            f"Current: {current_display}, Historical: {historical_display}. "
            f"Degradation score: {degradation_score:.2f}"
        )
        
        return message
    
    def _generate_alert_recommendation(self, metric_name: str, 
                                     severity: DegradationSeverity,
                                     degradation_score: float) -> str:
        """Generate recommendation for alert."""
        
        if severity == DegradationSeverity.CRITICAL:
            return "IMMEDIATE ACTION REQUIRED: Consider halting strategy and investigate root cause"
        elif severity == DegradationSeverity.SEVERE:
            return "URGENT: Reduce position sizes and schedule immediate strategy review"
        elif severity == DegradationSeverity.MODERATE:
            return "WARNING: Monitor closely and consider retraining model within 1-2 days"
        else:
            return "CAUTION: Continue monitoring and schedule routine model update"
    
    def _calculate_performance_trends(self, recent_performance: List[PerformanceMetrics]) -> Dict[str, float]:
        """Calculate trends in recent performance."""
        
        if len(recent_performance) < 3:
            return {}
        
        trends = {}
        
        metrics_to_trend = [
            ('sharpe_ratio', lambda m: m.sharpe_ratio or 0.0),
            ('win_rate', lambda m: m.win_rate),
            ('average_pnl', lambda m: m.average_pnl)
        ]
        
        for metric_name, extractor in metrics_to_trend:
            values = [extractor(m) for m in recent_performance if extractor(m) is not None]
            
            if len(values) >= 3:
                x = np.arange(len(values))
                try:
                    slope, _, _, _, _ = stats.linregress(x, values)
                    trends[f"{metric_name}_trend"] = float(slope)
                except:
                    trends[f"{metric_name}_trend"] = 0.0
        
        return trends
    
    def _estimate_time_to_failure(self, performance_trends: Dict[str, float],
                                degradation_scores: Dict[str, float]) -> Optional[float]:
        """Estimate time until strategy failure based on trends."""
        
        if not performance_trends or not degradation_scores:
            return None
        
        # Use Sharpe ratio trend as primary indicator
        sharpe_trend = performance_trends.get('sharpe_ratio_trend', 0.0)
        current_degradation = degradation_scores.get('sharpe_ratio', 0.0)
        
        if sharpe_trend >= 0:  # No negative trend
            return None
        
        # Estimate days until critical degradation (score = 0.8)
        degradation_to_failure = 0.8 - current_degradation
        if degradation_to_failure <= 0:
            return 0.0  # Already at failure level
        
        # Assuming linear degradation rate based on trend
        daily_degradation_rate = abs(sharpe_trend) * 0.1  # Scale factor
        
        if daily_degradation_rate > 0:
            days_to_failure = degradation_to_failure / daily_degradation_rate
            return min(365.0, max(1.0, days_to_failure))  # Cap between 1 day and 1 year
        
        return None
    
    def _calculate_degradation_confidence(self, degradation_scores: Dict[str, float],
                                        recent_sample_size: int,
                                        historical_sample_size: int) -> float:
        """Calculate confidence in degradation detection."""
        
        # Base confidence on sample sizes
        min_sample_confidence = min(
            1.0, (recent_sample_size + historical_sample_size) / 40.0
        )
        
        # Adjust based on consistency of degradation across metrics
        degradation_values = list(degradation_scores.values())
        if degradation_values:
            degradation_consistency = 1.0 - (np.std(degradation_values) / np.mean(degradation_values) 
                                            if np.mean(degradation_values) > 0 else 0.0)
            degradation_consistency = max(0.0, min(1.0, degradation_consistency))
        else:
            degradation_consistency = 0.0
        
        # Combined confidence
        confidence = (min_sample_confidence * 0.6 + degradation_consistency * 0.4)
        
        return max(0.1, min(0.99, confidence))
    
    def _identify_key_degraded_metrics(self, degradation_scores: Dict[str, float],
                                     threshold: float = 0.3) -> List[str]:
        """Identify metrics showing significant degradation."""
        
        return [
            metric for metric, score in degradation_scores.items()
            if score >= threshold
        ]
    
    def _analyze_recent_performance_changes(self, recent_performance: List[PerformanceMetrics]) -> Dict[str, float]:
        """Analyze recent changes in performance."""
        
        if len(recent_performance) < 2:
            return {}
        
        changes = {}
        
        # Compare most recent vs. earlier recent performance
        recent_half = recent_performance[len(recent_performance)//2:]
        earlier_half = recent_performance[:len(recent_performance)//2]
        
        metrics_to_compare = [
            ('sharpe_ratio', lambda m: m.sharpe_ratio or 0.0),
            ('win_rate', lambda m: m.win_rate),
            ('average_pnl', lambda m: m.average_pnl)
        ]
        
        for metric_name, extractor in metrics_to_compare:
            recent_values = [extractor(m) for m in recent_half if extractor(m) is not None]
            earlier_values = [extractor(m) for m in earlier_half if extractor(m) is not None]
            
            if recent_values and earlier_values:
                recent_mean = np.mean(recent_values)
                earlier_mean = np.mean(earlier_values)
                
                if earlier_mean != 0:
                    pct_change = (recent_mean - earlier_mean) / abs(earlier_mean)
                    changes[f"{metric_name}_recent_change"] = pct_change
        
        return changes
    
    def _build_historical_context(self, historical_baseline: List[PerformanceMetrics],
                                degradation_scores: Dict[str, float]) -> Dict[str, Any]:
        """Build historical context for degradation analysis."""
        
        context = {}
        
        # Historical performance statistics
        if historical_baseline:
            sharpe_values = [m.sharpe_ratio or 0.0 for m in historical_baseline]
            win_rates = [m.win_rate for m in historical_baseline]
            
            context['historical_sharpe_mean'] = np.mean(sharpe_values)
            context['historical_sharpe_std'] = np.std(sharpe_values)
            context['historical_win_rate_mean'] = np.mean(win_rates)
            context['historical_sample_size'] = len(historical_baseline)
            
            # Performance percentiles for current degradation
            if sharpe_values:
                context['current_performance_percentile'] = {
                    metric: stats.percentileofscore(sharpe_values, 1.0 - score)
                    for metric, score in degradation_scores.items()
                    if metric == 'sharpe_ratio'
                }
        
        return context
    
    def _generate_degradation_recommendation(self, severity: DegradationSeverity,
                                           alerts: List[DegradationAlert],
                                           key_degraded_metrics: List[str]) -> str:
        """Generate overall recommendation for degradation response."""
        
        if severity == DegradationSeverity.CRITICAL:
            return ("CRITICAL DEGRADATION DETECTED: Immediately halt automated trading, "
                   "reduce position sizes to minimum, and conduct emergency strategy review. "
                   "Do not resume trading until root cause is identified and addressed.")
        
        elif severity == DegradationSeverity.SEVERE:
            return ("SEVERE DEGRADATION DETECTED: Reduce position sizes by 50-75%, "
                   "increase monitoring frequency to daily, and schedule immediate "
                   "model retraining. Consider temporary manual oversight of trades.")
        
        elif severity == DegradationSeverity.MODERATE:
            return ("MODERATE DEGRADATION DETECTED: Reduce position sizes by 25-50%, "
                   "schedule model retraining within 2-3 days, and increase monitoring "
                   "frequency. Focus on improving degraded metrics: " + 
                   ", ".join(key_degraded_metrics))
        
        elif severity == DegradationSeverity.MILD:
            return ("MILD DEGRADATION DETECTED: Continue current operations with increased "
                   "monitoring. Schedule routine model update within 1 week. "
                   "Monitor key metrics: " + ", ".join(key_degraded_metrics))
        
        else:
            return ("NO SIGNIFICANT DEGRADATION: Continue normal operations. "
                   "Maintain regular monitoring schedule.")
    
    def _calculate_degradation_rate(self, degradation_scores: Dict[str, float]) -> float:
        """Calculate overall degradation rate."""
        
        if not degradation_scores:
            return 0.0
        
        # Weight different metrics by importance
        metric_weights = {
            'sharpe_ratio': 0.4,
            'win_rate': 0.3,
            'profit_factor': 0.2,
            'average_pnl': 0.1
        }
        
        weighted_degradation = 0.0
        total_weight = 0.0
        
        for metric, score in degradation_scores.items():
            weight = metric_weights.get(metric, 0.1)
            weighted_degradation += score * weight
            total_weight += weight
        
        if total_weight > 0:
            return weighted_degradation / total_weight
        else:
            return np.mean(list(degradation_scores.values()))
    
    def _determine_monitoring_interval(self, severity: DegradationSeverity,
                                     confidence: float) -> timedelta:
        """Determine next monitoring interval based on severity and confidence."""
        
        base_intervals = {
            DegradationSeverity.CRITICAL: timedelta(hours=6),
            DegradationSeverity.SEVERE: timedelta(hours=12),
            DegradationSeverity.MODERATE: timedelta(days=1),
            DegradationSeverity.MILD: timedelta(days=3),
            DegradationSeverity.NONE: timedelta(days=7)
        }
        
        base_interval = base_intervals.get(severity, timedelta(days=1))
        
        # Adjust based on confidence
        confidence_multiplier = 2.0 - confidence  # Higher confidence = shorter interval
        
        adjusted_interval = base_interval * confidence_multiplier
        
        # Cap intervals
        min_interval = timedelta(hours=1)
        max_interval = timedelta(days=14)
        
        return max(min_interval, min(max_interval, adjusted_interval))
    
    # Helper methods for persistence testing
    
    def _calculate_autocorrelations(self, performance_metrics: List[PerformanceMetrics],
                                  max_lag: int) -> Dict[int, float]:
        """Calculate autocorrelations for different lags."""
        
        # Extract Sharpe ratios as primary performance metric
        sharpe_ratios = [m.sharpe_ratio or 0.0 for m in performance_metrics]
        
        autocorrelations = {}
        
        for lag in range(1, max_lag + 1):
            if len(sharpe_ratios) > lag:
                # Calculate Pearson correlation between series and lagged series
                original = sharpe_ratios[lag:]
                lagged = sharpe_ratios[:-lag]
                
                if len(original) > 1 and len(lagged) > 1:
                    try:
                        correlation = np.corrcoef(original, lagged)[0, 1]
                        autocorrelations[lag] = correlation if not np.isnan(correlation) else 0.0
                    except:
                        autocorrelations[lag] = 0.0
                else:
                    autocorrelations[lag] = 0.0
        
        return autocorrelations
    
    def _calculate_persistence_score(self, autocorrelations: Dict[int, float]) -> float:
        """Calculate overall persistence score from autocorrelations."""
        
        if not autocorrelations:
            return 0.0
        
        # Weight shorter lags more heavily
        weights = {lag: 1.0 / lag for lag in autocorrelations.keys()}
        total_weight = sum(weights.values())
        
        if total_weight == 0:
            return 0.0
        
        weighted_correlation = sum(
            autocorrelations[lag] * weights[lag]
            for lag in autocorrelations.keys()
        )
        
        persistence_score = weighted_correlation / total_weight
        
        # Normalize to 0-1 scale (0 = no persistence, 1 = perfect persistence)
        return max(0.0, min(1.0, (persistence_score + 1.0) / 2.0))
    
    def _test_mean_reversion_tendency(self, performance_metrics: List[PerformanceMetrics]) -> float:
        """Test for mean reversion tendency in performance."""
        
        if len(performance_metrics) < 3:
            return 0.0
        
        sharpe_ratios = [m.sharpe_ratio or 0.0 for m in performance_metrics]
        
        # Calculate mean
        mean_sharpe = np.mean(sharpe_ratios)
        
        # Test for mean reversion: correlation between (value - mean) and next period change
        mean_deviations = []
        next_changes = []
        
        for i in range(len(sharpe_ratios) - 1):
            deviation = sharpe_ratios[i] - mean_sharpe
            next_change = sharpe_ratios[i + 1] - sharpe_ratios[i]
            
            mean_deviations.append(deviation)
            next_changes.append(next_change)
        
        if len(mean_deviations) > 1:
            try:
                # Negative correlation indicates mean reversion
                correlation = np.corrcoef(mean_deviations, next_changes)[0, 1]
                mean_reversion_tendency = -correlation if not np.isnan(correlation) else 0.0
                return max(0.0, min(1.0, mean_reversion_tendency))
            except:
                return 0.0
        
        return 0.0
    
    def _analyze_performance_streaks(self, performance_metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """Analyze winning and losing streaks in performance."""
        
        if len(performance_metrics) < 2:
            return {}
        
        sharpe_ratios = [m.sharpe_ratio or 0.0 for m in performance_metrics]
        mean_sharpe = np.mean(sharpe_ratios)
        
        # Classify periods as above/below mean
        above_mean = [sr > mean_sharpe for sr in sharpe_ratios]
        
        # Find streaks
        streaks = []
        current_streak_length = 1
        current_streak_type = above_mean[0]
        
        for i in range(1, len(above_mean)):
            if above_mean[i] == current_streak_type:
                current_streak_length += 1
            else:
                streaks.append((current_streak_type, current_streak_length))
                current_streak_type = above_mean[i]
                current_streak_length = 1
        
        # Add final streak
        streaks.append((current_streak_type, current_streak_length))
        
        # Analyze streaks
        positive_streaks = [length for is_positive, length in streaks if is_positive]
        negative_streaks = [length for is_positive, length in streaks if not is_positive]
        
        analysis = {
            'total_streaks': len(streaks),
            'positive_streaks_count': len(positive_streaks),
            'negative_streaks_count': len(negative_streaks),
            'avg_positive_streak_length': np.mean(positive_streaks) if positive_streaks else 0.0,
            'avg_negative_streak_length': np.mean(negative_streaks) if negative_streaks else 0.0,
            'max_positive_streak_length': max(positive_streaks) if positive_streaks else 0,
            'max_negative_streak_length': max(negative_streaks) if negative_streaks else 0,
            'streak_ratio': len(positive_streaks) / len(streaks) if streaks else 0.0
        }
        
        return analysis
    
    def _identify_momentum_reversal_periods(self, dates: List[datetime],
                                          performance_metrics: List[PerformanceMetrics]
                                          ) -> Tuple[List[Tuple[datetime, datetime]], List[Tuple[datetime, datetime]]]:
        """Identify momentum and reversal periods."""
        
        if len(performance_metrics) < 5:
            return [], []
        
        sharpe_ratios = [m.sharpe_ratio or 0.0 for m in performance_metrics]
        
        # Calculate rolling trends
        window = min(5, len(sharpe_ratios) // 3)
        trends = []
        
        for i in range(window, len(sharpe_ratios)):
            window_data = sharpe_ratios[i-window:i]
            x = np.arange(len(window_data))
            try:
                slope, _, _, _, _ = stats.linregress(x, window_data)
                trends.append(slope)
            except:
                trends.append(0.0)
        
        # Identify momentum (consistent positive trends) and reversal (trend changes) periods
        momentum_periods = []
        reversal_periods = []
        
        # Simple momentum detection: sequences of positive trends
        momentum_threshold = 0.01
        reversal_threshold = 0.02
        
        in_momentum = False
        in_reversal = False
        period_start = None
        
        for i, trend in enumerate(trends):
            date_index = i + window
            
            # Momentum detection
            is_momentum = trend > momentum_threshold
            if is_momentum and not in_momentum:
                period_start = dates[date_index]
                in_momentum = True
            elif not is_momentum and in_momentum:
                momentum_periods.append((period_start, dates[date_index]))
                in_momentum = False
            
            # Reversal detection (significant trend change)
            if i > 0:
                trend_change = abs(trend - trends[i-1])
                is_reversal = trend_change > reversal_threshold
                
                if is_reversal and not in_reversal:
                    period_start = dates[date_index]
                    in_reversal = True
                elif not is_reversal and in_reversal:
                    reversal_periods.append((period_start, dates[date_index]))
                    in_reversal = False
        
        # Close any open periods
        if in_momentum and period_start:
            momentum_periods.append((period_start, dates[-1]))
        if in_reversal and period_start:
            reversal_periods.append((period_start, dates[-1]))
        
        return momentum_periods, reversal_periods
    
    def _test_persistence_significance(self, autocorrelations: Dict[int, float],
                                     sample_size: int) -> Dict[str, float]:
        """Test statistical significance of persistence measures."""
        
        significance_tests = {}
        
        for lag, correlation in autocorrelations.items():
            if sample_size > lag + 2:
                # Test if autocorrelation is significantly different from zero
                standard_error = 1.0 / np.sqrt(sample_size - lag)
                t_stat = correlation / standard_error
                
                # Two-tailed test
                p_value = 2 * (1 - stats.t.cdf(abs(t_stat), sample_size - lag - 1))
                
                significance_tests[f'lag_{lag}_p_value'] = p_value
                significance_tests[f'lag_{lag}_significant'] = p_value < self.config.significance_level
        
        return significance_tests
    
    def _calculate_predictability_metrics(self, performance_metrics: List[PerformanceMetrics],
                                        autocorrelations: Dict[int, float]) -> Dict[str, float]:
        """Calculate predictability metrics based on persistence analysis."""
        
        if not autocorrelations:
            return {}
        
        metrics = {}
        
        # Predictability based on autocorrelation strength
        max_autocorr = max(autocorrelations.values())
        min_autocorr = min(autocorrelations.values())
        
        metrics['max_autocorrelation'] = max_autocorr
        metrics['min_autocorrelation'] = min_autocorr
        metrics['autocorr_range'] = max_autocorr - min_autocorr
        
        # Predictability score (0-1, higher means more predictable)
        predictability = abs(max_autocorr)  # Strong positive or negative correlation = predictable
        metrics['predictability_score'] = min(1.0, predictability)
        
        # Model potential based on persistence patterns
        if max_autocorr > 0.3:
            metrics['momentum_model_potential'] = max_autocorr
        else:
            metrics['momentum_model_potential'] = 0.0
        
        if min_autocorr < -0.3:
            metrics['mean_reversion_model_potential'] = abs(min_autocorr)
        else:
            metrics['mean_reversion_model_potential'] = 0.0
        
        return metrics
    
    def _analyze_regime_specific_persistence(self, dates: List[datetime],
                                           performance_metrics: List[PerformanceMetrics]
                                           ) -> Optional[Dict[str, float]]:
        """Analyze persistence within different market regimes."""
        
        # This would require VIX data integration - placeholder for future implementation
        # For now, return None to indicate regime analysis not available
        return None