"""
Out-of-Sample Validator for trading strategy robustness testing.

This service implements walk-forward analysis methods including anchored,
rolling window, and expanding window validation to assess strategy 
robustness and prevent overfitting in time-bin trading strategies.

Requirements: 3.1, 3.2, 3.3
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import warnings
from loguru import logger
from sqlalchemy.orm import Session
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, mean_absolute_error
from scipy import stats
import itertools

from ..time_bin_analyzer import TimeBinAnalyzer, TimeBin, TimeBinMetrics
from ..statistical_testing_engine import StatisticalTestingEngine, BootstrapResult
from ...models.database import ProcessedTrade
from ...database.connection import get_db_session


class ValidationMethod(Enum):
    """Types of walk-forward validation methods."""
    ANCHORED_WALK_FORWARD = "anchored_walk_forward"
    ROLLING_WINDOW = "rolling_window"  
    EXPANDING_WINDOW = "expanding_window"
    TIME_SERIES_CROSS_VALIDATION = "time_series_cv"


class RobustnessMetric(Enum):
    """Metrics for assessing strategy robustness."""
    SHARPE_RATIO = "sharpe_ratio"
    CALMAR_RATIO = "calmar_ratio"
    SORTINO_RATIO = "sortino_ratio"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    AVERAGE_PNL = "average_pnl"
    MAX_DRAWDOWN = "max_drawdown"
    VOLATILITY = "volatility"


@dataclass
class ValidationPeriod:
    """Container for validation period configuration."""
    in_sample_start: datetime
    in_sample_end: datetime
    out_of_sample_start: datetime
    out_of_sample_end: datetime
    period_id: str
    trades_in_sample: int = 0
    trades_out_of_sample: int = 0


@dataclass
class PeriodPerformance:
    """Performance metrics for a validation period."""
    period_id: str
    validation_method: ValidationMethod
    in_sample_metrics: TimeBinMetrics
    out_of_sample_metrics: TimeBinMetrics
    performance_degradation: Dict[str, float]
    statistical_significance: Dict[str, float]
    robustness_score: float
    period_config: ValidationPeriod
    calculation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class WalkForwardResults:
    """Complete walk-forward validation results."""
    validation_method: ValidationMethod
    time_bin: TimeBin
    total_periods: int
    period_performances: List[PeriodPerformance]
    overall_robustness_metrics: Dict[str, float]
    stability_analysis: Dict[str, Any]
    overfitting_indicators: Dict[str, float]
    performance_consistency: Dict[str, float]
    cross_validation_summary: Optional[Dict[str, Any]]
    recommendation: str
    validation_config: Dict[str, Any]
    generation_timestamp: datetime = field(default_factory=datetime.now)


@dataclass 
class CrossValidationConfig:
    """Configuration for time-series cross-validation."""
    n_splits: int = 5
    test_size: Optional[int] = None  # Number of test periods, None for auto
    gap: int = 0  # Gap between train and test sets
    max_train_size: Optional[int] = None  # Maximum training periods
    expanding_window: bool = False  # Use expanding window instead of rolling


@dataclass
class RobustnessTestConfig:
    """Configuration for robustness testing."""
    min_trades_per_period: int = 30
    min_validation_periods: int = 3
    confidence_level: float = 0.95
    bootstrap_samples: int = 1000
    performance_degradation_threshold: float = 0.20  # 20% degradation threshold
    stability_threshold: float = 0.15  # 15% coefficient of variation threshold
    overfitting_detection_threshold: float = 0.30  # 30% in-sample vs out-sample gap
    

class OutOfSampleValidator:
    """
    Comprehensive out-of-sample validation engine for trading strategies.
    
    Implements multiple walk-forward analysis methods to assess strategy
    robustness, detect overfitting, and provide confidence in time-bin
    trading strategy performance.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the out-of-sample validator."""
        self.db_session = db_session or get_db_session()
        self.time_bin_analyzer = TimeBinAnalyzer(db_session=self.db_session)
        self.statistical_engine = StatisticalTestingEngine()
        
        # Default configuration
        self.default_config = RobustnessTestConfig()
        
        logger.info("OutOfSampleValidator initialized")
    
    def anchored_walk_forward(self, 
                            time_bin: TimeBin,
                            initial_window_months: int = 6,
                            step_months: int = 1,
                            out_of_sample_months: int = 1,
                            end_date: Optional[datetime] = None,
                            config: Optional[RobustnessTestConfig] = None) -> WalkForwardResults:
        """
        Perform anchored walk-forward validation with expanding in-sample window.
        
        In anchored walk-forward, the training window starts from a fixed point
        and expands forward, while the test window moves forward in steps.
        This method tests strategy robustness as more data becomes available.
        
        Args:
            time_bin: Time bin configuration to validate
            initial_window_months: Initial training window size in months
            step_months: Step size for moving forward in months
            out_of_sample_months: Out-of-sample test period length
            end_date: End date for validation (defaults to latest data)
            config: Robustness testing configuration
            
        Returns:
            WalkForwardResults with complete validation analysis
        """
        logger.info("Starting anchored walk-forward validation for time bin {}:{}:{:02d}", 
                   time_bin.account_name, time_bin.hour, time_bin.minute_bin)
        
        config = config or self.default_config
        
        try:
            # Get all trades for the time bin
            all_trades = self.time_bin_analyzer.get_time_bin_trades(time_bin)
            if len(all_trades) < config.min_trades_per_period * 2:
                raise ValueError(f"Insufficient trades ({len(all_trades)}) for walk-forward validation")
            
            # Create validation periods
            validation_periods = self._create_anchored_periods(
                all_trades, initial_window_months, step_months, 
                out_of_sample_months, end_date
            )
            
            if len(validation_periods) < config.min_validation_periods:
                raise ValueError(f"Insufficient validation periods ({len(validation_periods)})")
            
            # Perform validation for each period
            period_performances = []
            for period in validation_periods:
                try:
                    performance = self._validate_period(time_bin, period, config)
                    performance.validation_method = ValidationMethod.ANCHORED_WALK_FORWARD
                    period_performances.append(performance)
                except Exception as e:
                    logger.warning("Failed to validate period {}: {}", period.period_id, e)
                    continue
            
            # Analyze overall results
            overall_metrics = self._calculate_overall_robustness(period_performances, config)
            stability_analysis = self._analyze_stability(period_performances)
            overfitting_indicators = self._detect_overfitting(period_performances, config)
            consistency_metrics = self._analyze_consistency(period_performances)
            
            # Generate recommendation
            recommendation = self._generate_recommendation(
                overall_metrics, stability_analysis, overfitting_indicators, config
            )
            
            results = WalkForwardResults(
                validation_method=ValidationMethod.ANCHORED_WALK_FORWARD,
                time_bin=time_bin,
                total_periods=len(period_performances),
                period_performances=period_performances,
                overall_robustness_metrics=overall_metrics,
                stability_analysis=stability_analysis,
                overfitting_indicators=overfitting_indicators,
                performance_consistency=consistency_metrics,
                cross_validation_summary=None,
                recommendation=recommendation,
                validation_config={
                    "initial_window_months": initial_window_months,
                    "step_months": step_months,
                    "out_of_sample_months": out_of_sample_months,
                    "config": config.__dict__
                }
            )
            
            logger.info("Anchored walk-forward validation completed: {} periods, robustness score: {:.3f}", 
                       len(period_performances), overall_metrics.get('overall_robustness_score', 0))
            
            return results
            
        except Exception as e:
            logger.error("Anchored walk-forward validation failed: {}", e)
            raise ValueError(f"Walk-forward validation failed: {e}")
    
    def rolling_window_validation(self,
                                time_bin: TimeBin,
                                window_months: int = 6,
                                step_months: int = 1,
                                out_of_sample_months: int = 1,
                                min_periods: int = 5,
                                config: Optional[RobustnessTestConfig] = None) -> WalkForwardResults:
        """
        Perform rolling window validation with fixed-size training windows.
        
        Rolling window validation uses a fixed-size training window that
        slides forward through time, providing consistent sample sizes
        and testing strategy stability across different market conditions.
        
        Args:
            time_bin: Time bin configuration to validate
            window_months: Fixed training window size in months
            step_months: Step size for moving window forward
            out_of_sample_months: Out-of-sample test period length
            min_periods: Minimum number of validation periods required
            config: Robustness testing configuration
            
        Returns:
            WalkForwardResults with rolling window validation analysis
        """
        logger.info("Starting rolling window validation for time bin {}:{}:{:02d}", 
                   time_bin.account_name, time_bin.hour, time_bin.minute_bin)
        
        config = config or self.default_config
        
        try:
            # Get all trades
            all_trades = self.time_bin_analyzer.get_time_bin_trades(time_bin)
            if len(all_trades) < config.min_trades_per_period * min_periods:
                raise ValueError(f"Insufficient trades for rolling window validation")
            
            # Create rolling window periods
            validation_periods = self._create_rolling_periods(
                all_trades, window_months, step_months, out_of_sample_months, min_periods
            )
            
            # Validate each period
            period_performances = []
            for period in validation_periods:
                try:
                    performance = self._validate_period(time_bin, period, config)
                    performance.validation_method = ValidationMethod.ROLLING_WINDOW
                    period_performances.append(performance)
                except Exception as e:
                    logger.warning("Failed to validate rolling period {}: {}", period.period_id, e)
                    continue
            
            # Analyze results
            overall_metrics = self._calculate_overall_robustness(period_performances, config)
            stability_analysis = self._analyze_stability(period_performances)
            overfitting_indicators = self._detect_overfitting(period_performances, config)
            consistency_metrics = self._analyze_consistency(period_performances)
            
            recommendation = self._generate_recommendation(
                overall_metrics, stability_analysis, overfitting_indicators, config
            )
            
            results = WalkForwardResults(
                validation_method=ValidationMethod.ROLLING_WINDOW,
                time_bin=time_bin,
                total_periods=len(period_performances),
                period_performances=period_performances,
                overall_robustness_metrics=overall_metrics,
                stability_analysis=stability_analysis,
                overfitting_indicators=overfitting_indicators,
                performance_consistency=consistency_metrics,
                cross_validation_summary=None,
                recommendation=recommendation,
                validation_config={
                    "window_months": window_months,
                    "step_months": step_months,
                    "out_of_sample_months": out_of_sample_months,
                    "min_periods": min_periods,
                    "config": config.__dict__
                }
            )
            
            logger.info("Rolling window validation completed: {} periods, robustness score: {:.3f}", 
                       len(period_performances), overall_metrics.get('overall_robustness_score', 0))
            
            return results
            
        except Exception as e:
            logger.error("Rolling window validation failed: {}", e)
            raise ValueError(f"Rolling window validation failed: {e}")
    
    def expanding_window_validation(self,
                                  time_bin: TimeBin,
                                  initial_window_months: int = 3,
                                  expansion_months: int = 1,
                                  out_of_sample_months: int = 1,
                                  max_periods: int = 12,
                                  config: Optional[RobustnessTestConfig] = None) -> WalkForwardResults:
        """
        Perform expanding window validation with growing training datasets.
        
        Expanding window validation starts with a small training window
        and progressively expands it, testing how strategy performance
        changes as more historical data becomes available.
        
        Args:
            time_bin: Time bin configuration to validate
            initial_window_months: Initial training window size
            expansion_months: How much to expand window each period
            out_of_sample_months: Out-of-sample test period length
            max_periods: Maximum number of validation periods
            config: Robustness testing configuration
            
        Returns:
            WalkForwardResults with expanding window validation analysis
        """
        logger.info("Starting expanding window validation for time bin {}:{}:{:02d}", 
                   time_bin.account_name, time_bin.hour, time_bin.minute_bin)
        
        config = config or self.default_config
        
        try:
            # Get all trades
            all_trades = self.time_bin_analyzer.get_time_bin_trades(time_bin)
            if len(all_trades) < config.min_trades_per_period * 3:
                raise ValueError(f"Insufficient trades for expanding window validation")
            
            # Create expanding window periods
            validation_periods = self._create_expanding_periods(
                all_trades, initial_window_months, expansion_months, 
                out_of_sample_months, max_periods
            )
            
            # Validate each period
            period_performances = []
            for period in validation_periods:
                try:
                    performance = self._validate_period(time_bin, period, config)
                    performance.validation_method = ValidationMethod.EXPANDING_WINDOW
                    period_performances.append(performance)
                except Exception as e:
                    logger.warning("Failed to validate expanding period {}: {}", period.period_id, e)
                    continue
            
            # Analyze results with focus on learning curve
            overall_metrics = self._calculate_overall_robustness(period_performances, config)
            stability_analysis = self._analyze_stability(period_performances)
            learning_curve_analysis = self._analyze_learning_curve(period_performances)
            overfitting_indicators = self._detect_overfitting(period_performances, config)
            consistency_metrics = self._analyze_consistency(period_performances)
            
            # Add learning curve to stability analysis
            stability_analysis.update(learning_curve_analysis)
            
            recommendation = self._generate_recommendation(
                overall_metrics, stability_analysis, overfitting_indicators, config
            )
            
            results = WalkForwardResults(
                validation_method=ValidationMethod.EXPANDING_WINDOW,
                time_bin=time_bin,
                total_periods=len(period_performances),
                period_performances=period_performances,
                overall_robustness_metrics=overall_metrics,
                stability_analysis=stability_analysis,
                overfitting_indicators=overfitting_indicators,
                performance_consistency=consistency_metrics,
                cross_validation_summary=None,
                recommendation=recommendation,
                validation_config={
                    "initial_window_months": initial_window_months,
                    "expansion_months": expansion_months,
                    "out_of_sample_months": out_of_sample_months,
                    "max_periods": max_periods,
                    "config": config.__dict__
                }
            )
            
            logger.info("Expanding window validation completed: {} periods, robustness score: {:.3f}", 
                       len(period_performances), overall_metrics.get('overall_robustness_score', 0))
            
            return results
            
        except Exception as e:
            logger.error("Expanding window validation failed: {}", e)
            raise ValueError(f"Expanding window validation failed: {e}")
    
    def time_series_cross_validation(self,
                                   time_bin: TimeBin,
                                   cv_config: Optional[CrossValidationConfig] = None,
                                   robustness_config: Optional[RobustnessTestConfig] = None) -> WalkForwardResults:
        """
        Perform time-series cross-validation for strategy robustness assessment.
        
        Uses scikit-learn's TimeSeriesSplit to create multiple train/test splits
        while respecting temporal order, providing a comprehensive assessment
        of strategy performance across different time periods.
        
        Args:
            time_bin: Time bin configuration to validate
            cv_config: Cross-validation configuration
            robustness_config: Robustness testing configuration
            
        Returns:
            WalkForwardResults with cross-validation analysis
        """
        logger.info("Starting time-series cross-validation for time bin {}:{}:{:02d}", 
                   time_bin.account_name, time_bin.hour, time_bin.minute_bin)
        
        cv_config = cv_config or CrossValidationConfig()
        robustness_config = robustness_config or self.default_config
        
        try:
            # Get all trades
            all_trades = self.time_bin_analyzer.get_time_bin_trades(time_bin)
            if len(all_trades) < robustness_config.min_trades_per_period * cv_config.n_splits:
                raise ValueError(f"Insufficient trades for cross-validation")
            
            # Sort trades by timestamp
            sorted_trades = sorted(all_trades, key=lambda x: x.timestamp)
            
            # Create time series splits
            tscv = TimeSeriesSplit(
                n_splits=cv_config.n_splits,
                test_size=cv_config.test_size,
                gap=cv_config.gap,
                max_train_size=cv_config.max_train_size
            )
            
            # Create validation periods from CV splits
            validation_periods = []
            trade_indices = np.arange(len(sorted_trades))
            
            for fold_idx, (train_idx, test_idx) in enumerate(tscv.split(trade_indices)):
                train_trades = [sorted_trades[i] for i in train_idx]
                test_trades = [sorted_trades[i] for i in test_idx]
                
                if len(train_trades) < robustness_config.min_trades_per_period:
                    continue
                if len(test_trades) < robustness_config.min_trades_per_period:
                    continue
                
                period = ValidationPeriod(
                    in_sample_start=min(t.timestamp for t in train_trades),
                    in_sample_end=max(t.timestamp for t in train_trades),
                    out_of_sample_start=min(t.timestamp for t in test_trades),
                    out_of_sample_end=max(t.timestamp for t in test_trades),
                    period_id=f"cv_fold_{fold_idx + 1}",
                    trades_in_sample=len(train_trades),
                    trades_out_of_sample=len(test_trades)
                )
                validation_periods.append(period)
            
            # Validate each fold
            period_performances = []
            for period in validation_periods:
                try:
                    performance = self._validate_period(time_bin, period, robustness_config)
                    performance.validation_method = ValidationMethod.TIME_SERIES_CROSS_VALIDATION
                    period_performances.append(performance)
                except Exception as e:
                    logger.warning("Failed to validate CV fold {}: {}", period.period_id, e)
                    continue
            
            # Cross-validation specific analysis
            cv_summary = self._analyze_cross_validation_results(period_performances, cv_config)
            
            # Standard robustness analysis
            overall_metrics = self._calculate_overall_robustness(period_performances, robustness_config)
            stability_analysis = self._analyze_stability(period_performances)
            overfitting_indicators = self._detect_overfitting(period_performances, robustness_config)
            consistency_metrics = self._analyze_consistency(period_performances)
            
            recommendation = self._generate_recommendation(
                overall_metrics, stability_analysis, overfitting_indicators, robustness_config
            )
            
            results = WalkForwardResults(
                validation_method=ValidationMethod.TIME_SERIES_CROSS_VALIDATION,
                time_bin=time_bin,
                total_periods=len(period_performances),
                period_performances=period_performances,
                overall_robustness_metrics=overall_metrics,
                stability_analysis=stability_analysis,
                overfitting_indicators=overfitting_indicators,
                performance_consistency=consistency_metrics,
                cross_validation_summary=cv_summary,
                recommendation=recommendation,
                validation_config={
                    "cv_config": cv_config.__dict__,
                    "robustness_config": robustness_config.__dict__
                }
            )
            
            logger.info("Time-series cross-validation completed: {} folds, robustness score: {:.3f}", 
                       len(period_performances), overall_metrics.get('overall_robustness_score', 0))
            
            return results
            
        except Exception as e:
            logger.error("Time-series cross-validation failed: {}", e)
            raise ValueError(f"Cross-validation failed: {e}")
    
    def _create_anchored_periods(self, trades: List[ProcessedTrade], 
                               initial_window_months: int, step_months: int,
                               out_of_sample_months: int, 
                               end_date: Optional[datetime] = None) -> List[ValidationPeriod]:
        """Create validation periods for anchored walk-forward."""
        if not trades:
            return []
        
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)
        start_date = sorted_trades[0].timestamp
        end_date = end_date or sorted_trades[-1].timestamp
        
        periods = []
        anchor_date = start_date
        current_train_end = start_date + timedelta(days=initial_window_months * 30)
        
        period_id = 1
        while current_train_end < end_date:
            # Out-of-sample period
            oos_start = current_train_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=out_of_sample_months * 30)
            
            if oos_end > end_date:
                break
            
            # Count trades in periods
            train_trades = [t for t in sorted_trades 
                          if anchor_date <= t.timestamp <= current_train_end]
            test_trades = [t for t in sorted_trades 
                         if oos_start <= t.timestamp <= oos_end]
            
            if len(train_trades) >= self.default_config.min_trades_per_period and \
               len(test_trades) >= self.default_config.min_trades_per_period:
                
                period = ValidationPeriod(
                    in_sample_start=anchor_date,
                    in_sample_end=current_train_end,
                    out_of_sample_start=oos_start,
                    out_of_sample_end=oos_end,
                    period_id=f"anchored_{period_id}",
                    trades_in_sample=len(train_trades),
                    trades_out_of_sample=len(test_trades)
                )
                periods.append(period)
                period_id += 1
            
            # Move forward by step
            current_train_end += timedelta(days=step_months * 30)
        
        return periods
    
    def _create_rolling_periods(self, trades: List[ProcessedTrade],
                              window_months: int, step_months: int,
                              out_of_sample_months: int, min_periods: int) -> List[ValidationPeriod]:
        """Create validation periods for rolling window."""
        if not trades:
            return []
        
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)
        start_date = sorted_trades[0].timestamp
        end_date = sorted_trades[-1].timestamp
        
        periods = []
        current_start = start_date
        period_id = 1
        
        while current_start < end_date:
            # Training window
            train_end = current_start + timedelta(days=window_months * 30)
            if train_end >= end_date:
                break
            
            # Out-of-sample period
            oos_start = train_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=out_of_sample_months * 30)
            
            if oos_end > end_date:
                break
            
            # Count trades
            train_trades = [t for t in sorted_trades 
                          if current_start <= t.timestamp <= train_end]
            test_trades = [t for t in sorted_trades 
                         if oos_start <= t.timestamp <= oos_end]
            
            if len(train_trades) >= self.default_config.min_trades_per_period and \
               len(test_trades) >= self.default_config.min_trades_per_period:
                
                period = ValidationPeriod(
                    in_sample_start=current_start,
                    in_sample_end=train_end,
                    out_of_sample_start=oos_start,
                    out_of_sample_end=oos_end,
                    period_id=f"rolling_{period_id}",
                    trades_in_sample=len(train_trades),
                    trades_out_of_sample=len(test_trades)
                )
                periods.append(period)
                period_id += 1
            
            # Move window forward
            current_start += timedelta(days=step_months * 30)
            
            if len(periods) >= min_periods * 2:  # Reasonable upper limit
                break
        
        return periods[:min_periods * 2]  # Cap the number of periods
    
    def _create_expanding_periods(self, trades: List[ProcessedTrade],
                                initial_window_months: int, expansion_months: int,
                                out_of_sample_months: int, max_periods: int) -> List[ValidationPeriod]:
        """Create validation periods for expanding window."""
        if not trades:
            return []
        
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)
        start_date = sorted_trades[0].timestamp
        end_date = sorted_trades[-1].timestamp
        
        periods = []
        current_window_size = initial_window_months
        period_id = 1
        
        while period_id <= max_periods:
            # Training window (expanding)
            train_end = start_date + timedelta(days=current_window_size * 30)
            if train_end >= end_date:
                break
            
            # Out-of-sample period
            oos_start = train_end + timedelta(days=1)
            oos_end = oos_start + timedelta(days=out_of_sample_months * 30)
            
            if oos_end > end_date:
                break
            
            # Count trades
            train_trades = [t for t in sorted_trades 
                          if start_date <= t.timestamp <= train_end]
            test_trades = [t for t in sorted_trades 
                         if oos_start <= t.timestamp <= oos_end]
            
            if len(train_trades) >= self.default_config.min_trades_per_period and \
               len(test_trades) >= self.default_config.min_trades_per_period:
                
                period = ValidationPeriod(
                    in_sample_start=start_date,
                    in_sample_end=train_end,
                    out_of_sample_start=oos_start,
                    out_of_sample_end=oos_end,
                    period_id=f"expanding_{period_id}",
                    trades_in_sample=len(train_trades),
                    trades_out_of_sample=len(test_trades)
                )
                periods.append(period)
                period_id += 1
            
            # Expand window
            current_window_size += expansion_months
        
        return periods
    
    def _validate_period(self, time_bin: TimeBin, period: ValidationPeriod, 
                        config: RobustnessTestConfig) -> PeriodPerformance:
        """Validate a single period by calculating in-sample and out-of-sample metrics."""
        
        # Get trades for in-sample period
        in_sample_trades = [
            t for t in self.time_bin_analyzer.get_time_bin_trades(time_bin)
            if period.in_sample_start <= t.timestamp <= period.in_sample_end
        ]
        
        # Get trades for out-of-sample period
        out_sample_trades = [
            t for t in self.time_bin_analyzer.get_time_bin_trades(time_bin)
            if period.out_of_sample_start <= t.timestamp <= period.out_of_sample_end
        ]
        
        if len(in_sample_trades) < config.min_trades_per_period:
            raise ValueError(f"Insufficient in-sample trades: {len(in_sample_trades)}")
        if len(out_sample_trades) < config.min_trades_per_period:
            raise ValueError(f"Insufficient out-of-sample trades: {len(out_sample_trades)}")
        
        # Calculate metrics for both periods
        in_sample_metrics = self.time_bin_analyzer.calculate_time_bin_metrics(in_sample_trades)
        out_sample_metrics = self.time_bin_analyzer.calculate_time_bin_metrics(out_sample_trades)
        
        # Calculate performance degradation
        degradation = self._calculate_performance_degradation(in_sample_metrics, out_sample_metrics)
        
        # Statistical significance tests
        significance_tests = self._test_performance_significance(
            in_sample_trades, out_sample_trades, config
        )
        
        # Calculate robustness score for this period
        robustness_score = self._calculate_period_robustness_score(
            in_sample_metrics, out_sample_metrics, degradation, config
        )
        
        return PeriodPerformance(
            period_id=period.period_id,
            validation_method=ValidationMethod.ANCHORED_WALK_FORWARD,  # Will be updated by caller
            in_sample_metrics=in_sample_metrics,
            out_of_sample_metrics=out_sample_metrics,
            performance_degradation=degradation,
            statistical_significance=significance_tests,
            robustness_score=robustness_score,
            period_config=period
        )
    
    def _calculate_performance_degradation(self, in_sample: TimeBinMetrics, 
                                         out_sample: TimeBinMetrics) -> Dict[str, float]:
        """Calculate performance degradation between in-sample and out-of-sample."""
        degradation = {}
        
        metrics_to_compare = [
            ('sharpe_ratio', 'higher_better'),
            ('calmar_ratio', 'higher_better'),
            ('sortino_ratio', 'higher_better'),
            ('win_rate', 'higher_better'),
            ('profit_factor', 'higher_better'),
            ('average_pnl', 'higher_better'),
            ('volatility', 'lower_better'),
            ('max_drawdown', 'lower_better')
        ]
        
        for metric, direction in metrics_to_compare:
            in_val = getattr(in_sample, metric, 0)
            out_val = getattr(out_sample, metric, 0)
            
            if in_val != 0:
                if direction == 'higher_better':
                    degradation[f"{metric}_degradation"] = (in_val - out_val) / abs(in_val)
                else:
                    degradation[f"{metric}_degradation"] = (out_val - in_val) / abs(in_val)
            else:
                degradation[f"{metric}_degradation"] = 0.0
        
        return degradation
    
    def _test_performance_significance(self, in_sample_trades: List[ProcessedTrade],
                                     out_sample_trades: List[ProcessedTrade],
                                     config: RobustnessTestConfig) -> Dict[str, float]:
        """Test statistical significance of performance differences."""
        in_sample_pnl = [trade.pnl for trade in in_sample_trades]
        out_sample_pnl = [trade.pnl for trade in out_sample_trades]
        
        significance = {}
        
        # T-test for mean difference
        try:
            t_stat, t_pval = stats.ttest_ind(in_sample_pnl, out_sample_pnl)
            significance['mean_difference_t_test'] = float(t_pval)
        except:
            significance['mean_difference_t_test'] = 1.0
        
        # Mann-Whitney U test (non-parametric)
        try:
            mw_stat, mw_pval = stats.mannwhitneyu(
                in_sample_pnl, out_sample_pnl, alternative='two-sided'
            )
            significance['mann_whitney_test'] = float(mw_pval)
        except:
            significance['mann_whitney_test'] = 1.0
        
        # Kolmogorov-Smirnov test for distribution similarity
        try:
            ks_stat, ks_pval = stats.ks_2samp(in_sample_pnl, out_sample_pnl)
            significance['ks_distribution_test'] = float(ks_pval)
        except:
            significance['ks_distribution_test'] = 1.0
        
        return significance
    
    def _calculate_period_robustness_score(self, in_sample: TimeBinMetrics, 
                                         out_sample: TimeBinMetrics,
                                         degradation: Dict[str, float],
                                         config: RobustnessTestConfig) -> float:
        """Calculate robustness score for a single period."""
        score_components = []
        
        # Performance maintenance (lower degradation = higher score)
        key_metrics = ['sharpe_ratio_degradation', 'win_rate_degradation', 'average_pnl_degradation']
        avg_degradation = np.mean([abs(degradation.get(m, 0)) for m in key_metrics])
        performance_score = max(0, 1 - (avg_degradation / config.performance_degradation_threshold))
        score_components.append(performance_score * 0.4)
        
        # Absolute out-of-sample performance
        oos_sharpe = out_sample.sharpe_ratio if out_sample.sharpe_ratio is not None else 0
        oos_win_rate = out_sample.win_rate
        
        # Normalize scores (assuming good values: Sharpe > 1.0, Win Rate > 0.55)
        sharpe_score = min(1.0, max(0, oos_sharpe / 1.0)) if oos_sharpe > 0 else 0
        win_rate_score = min(1.0, max(0, (oos_win_rate - 0.5) / 0.1))
        
        score_components.append(sharpe_score * 0.3)
        score_components.append(win_rate_score * 0.3)
        
        return sum(score_components)
    
    def _calculate_overall_robustness(self, performances: List[PeriodPerformance],
                                    config: RobustnessTestConfig) -> Dict[str, float]:
        """Calculate overall robustness metrics across all periods."""
        if not performances:
            return {}
        
        # Individual robustness scores
        robustness_scores = [p.robustness_score for p in performances]
        
        # Performance degradation statistics
        all_degradations = {}
        for perf in performances:
            for metric, value in perf.performance_degradation.items():
                if metric not in all_degradations:
                    all_degradations[metric] = []
                all_degradations[metric].append(value)
        
        # Calculate summary statistics
        metrics = {
            'overall_robustness_score': float(np.mean(robustness_scores)),
            'robustness_stability': float(np.std(robustness_scores)),
            'min_robustness_score': float(np.min(robustness_scores)),
            'max_robustness_score': float(np.max(robustness_scores)),
            'periods_above_threshold': len([s for s in robustness_scores if s > 0.7]),
            'total_periods': len(performances)
        }
        
        # Add degradation summaries
        for metric, values in all_degradations.items():
            metrics[f"avg_{metric}"] = float(np.mean(values))
            metrics[f"std_{metric}"] = float(np.std(values))
        
        return metrics
    
    def _analyze_stability(self, performances: List[PeriodPerformance]) -> Dict[str, Any]:
        """Analyze stability of performance across periods."""
        if not performances:
            return {}
        
        # Extract key performance metrics across periods
        sharpe_ratios = [p.out_of_sample_metrics.sharpe_ratio or 0 for p in performances]
        win_rates = [p.out_of_sample_metrics.win_rate for p in performances]
        avg_pnls = [p.out_of_sample_metrics.average_pnl for p in performances]
        
        stability = {
            'sharpe_ratio_cv': float(np.std(sharpe_ratios) / np.mean(sharpe_ratios)) if np.mean(sharpe_ratios) != 0 else float('inf'),
            'win_rate_cv': float(np.std(win_rates) / np.mean(win_rates)) if np.mean(win_rates) != 0 else float('inf'),
            'pnl_cv': float(np.std(avg_pnls) / np.mean(avg_pnls)) if np.mean(avg_pnls) != 0 else float('inf'),
            'sharpe_trend': self._calculate_trend(sharpe_ratios),
            'performance_consistency': len([s for s in sharpe_ratios if s > 0]) / len(sharpe_ratios)
        }
        
        return stability
    
    def _analyze_learning_curve(self, performances: List[PeriodPerformance]) -> Dict[str, Any]:
        """Analyze learning curve for expanding window validation."""
        if len(performances) < 3:
            return {}
        
        # Extract performance over expanding windows
        robustness_scores = [p.robustness_score for p in performances]
        sample_sizes = [p.period_config.trades_in_sample for p in performances]
        
        # Calculate learning metrics
        learning_analysis = {
            'learning_curve_slope': self._calculate_trend(robustness_scores),
            'performance_vs_sample_size_correlation': float(np.corrcoef(sample_sizes, robustness_scores)[0, 1]) 
                if len(set(sample_sizes)) > 1 else 0.0,
            'early_vs_late_performance': robustness_scores[-1] - robustness_scores[0] if len(robustness_scores) > 1 else 0.0,
            'learning_stability': float(np.std(np.diff(robustness_scores))) if len(robustness_scores) > 1 else 0.0
        }
        
        return learning_analysis
    
    def _detect_overfitting(self, performances: List[PeriodPerformance], 
                          config: RobustnessTestConfig) -> Dict[str, float]:
        """Detect overfitting indicators."""
        if not performances:
            return {}
        
        # Calculate average gap between in-sample and out-of-sample performance
        sharpe_gaps = []
        win_rate_gaps = []
        
        for perf in performances:
            is_sharpe = perf.in_sample_metrics.sharpe_ratio or 0
            oos_sharpe = perf.out_of_sample_metrics.sharpe_ratio or 0
            sharpe_gaps.append(is_sharpe - oos_sharpe)
            
            is_win_rate = perf.in_sample_metrics.win_rate
            oos_win_rate = perf.out_of_sample_metrics.win_rate
            win_rate_gaps.append(is_win_rate - oos_win_rate)
        
        overfitting_indicators = {
            'avg_sharpe_gap': float(np.mean(sharpe_gaps)),
            'avg_win_rate_gap': float(np.mean(win_rate_gaps)),
            'sharpe_gap_consistency': float(np.std(sharpe_gaps)),
            'periods_with_large_gaps': len([g for g in sharpe_gaps if g > config.overfitting_detection_threshold]),
            'overfitting_risk_score': min(1.0, max(0, np.mean(sharpe_gaps) / config.overfitting_detection_threshold))
        }
        
        return overfitting_indicators
    
    def _analyze_consistency(self, performances: List[PeriodPerformance]) -> Dict[str, float]:
        """Analyze consistency of performance across periods."""
        if not performances:
            return {}
        
        # Count periods with positive performance
        positive_periods = len([p for p in performances 
                              if p.out_of_sample_metrics.average_pnl > 0])
        
        # Count periods with good Sharpe ratio
        good_sharpe_periods = len([p for p in performances 
                                 if (p.out_of_sample_metrics.sharpe_ratio or 0) > 1.0])
        
        # Count periods with good win rate
        good_win_rate_periods = len([p for p in performances 
                                   if p.out_of_sample_metrics.win_rate > 0.55])
        
        consistency = {
            'positive_period_ratio': positive_periods / len(performances),
            'good_sharpe_period_ratio': good_sharpe_periods / len(performances),
            'good_win_rate_period_ratio': good_win_rate_periods / len(performances),
            'overall_consistency_score': (positive_periods + good_sharpe_periods + good_win_rate_periods) / (3 * len(performances))
        }
        
        return consistency
    
    def _analyze_cross_validation_results(self, performances: List[PeriodPerformance],
                                        cv_config: CrossValidationConfig) -> Dict[str, Any]:
        """Analyze cross-validation specific metrics."""
        if not performances:
            return {}
        
        # Extract scores for CV analysis
        oos_sharpe_ratios = [p.out_of_sample_metrics.sharpe_ratio or 0 for p in performances]
        oos_win_rates = [p.out_of_sample_metrics.win_rate for p in performances]
        
        cv_summary = {
            'cv_mean_sharpe': float(np.mean(oos_sharpe_ratios)),
            'cv_std_sharpe': float(np.std(oos_sharpe_ratios)),
            'cv_mean_win_rate': float(np.mean(oos_win_rates)),
            'cv_std_win_rate': float(np.std(oos_win_rates)),
            'cv_score_stability': float(np.std(oos_sharpe_ratios) / np.mean(oos_sharpe_ratios)) if np.mean(oos_sharpe_ratios) != 0 else float('inf'),
            'folds_completed': len(performances),
            'folds_requested': cv_config.n_splits
        }
        
        # Confidence intervals
        if len(oos_sharpe_ratios) > 1:
            cv_summary['sharpe_confidence_interval'] = stats.t.interval(
                0.95, len(oos_sharpe_ratios)-1, 
                loc=np.mean(oos_sharpe_ratios), 
                scale=stats.sem(oos_sharpe_ratios)
            )
        
        return cv_summary
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend in a series of values using linear regression slope."""
        if len(values) < 2:
            return 0.0
        
        x = np.arange(len(values))
        try:
            slope, _, _, _, _ = stats.linregress(x, values)
            return float(slope)
        except:
            return 0.0
    
    def _generate_recommendation(self, overall_metrics: Dict[str, float],
                               stability_analysis: Dict[str, Any],
                               overfitting_indicators: Dict[str, float],
                               config: RobustnessTestConfig) -> str:
        """Generate recommendation based on validation results."""
        
        robustness_score = overall_metrics.get('overall_robustness_score', 0)
        overfitting_risk = overfitting_indicators.get('overfitting_risk_score', 0)
        stability_score = 1.0 / (1.0 + stability_analysis.get('sharpe_ratio_cv', float('inf')))
        
        if robustness_score > 0.8 and overfitting_risk < 0.3 and stability_score > 0.7:
            return "HIGHLY_RECOMMENDED - Strategy shows excellent robustness with low overfitting risk"
        elif robustness_score > 0.6 and overfitting_risk < 0.5 and stability_score > 0.6:
            return "RECOMMENDED - Strategy demonstrates good robustness with acceptable stability"
        elif robustness_score > 0.4 and overfitting_risk < 0.7:
            return "CONDITIONAL - Strategy shows moderate robustness, monitor carefully"
        elif overfitting_risk > 0.8:
            return "NOT_RECOMMENDED - High overfitting risk detected, strategy may not generalize"
        else:
            return "NOT_RECOMMENDED - Poor robustness metrics, consider strategy revision"