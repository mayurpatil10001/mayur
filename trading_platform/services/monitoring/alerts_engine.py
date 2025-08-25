"""
AlertsEngine for performance degradation detection and graduated alert system.

This module provides comprehensive alert management for trading strategy performance
degradation, including statistical testing, graduated severity levels, recommendation
updates, and user notification systems.

Requirements: 8.4, 8.5, 8.6
"""

import logging
import asyncio
import smtplib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart
import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy.orm import Session
from threading import Lock, Event
import json
import statistics

from ..time_bin_analyzer import TimeBinAnalyzer, TimeBin, SimpleTrade
from ..performance_metrics_calculator import PerformanceMetricsCalculator
from ..recommendation_engine import RecommendationEngine
from .time_bin_monitoring_service import (
    PerformanceSnapshot, MonitoringAlert, AlertSeverity, AnomalyType,
    TimeBinMonitoringService
)
from ...database.connection import get_db_session

logger = logging.getLogger(__name__)


class DegradationType(Enum):
    """Types of performance degradation."""
    STATISTICAL_DEGRADATION = "statistical_degradation"
    WIN_RATE_DECLINE = "win_rate_decline"
    PROFIT_FACTOR_DECLINE = "profit_factor_decline"
    SHARPE_RATIO_DECLINE = "sharpe_ratio_decline"
    MAXIMUM_DRAWDOWN_INCREASE = "maximum_drawdown_increase"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    AVERAGE_LOSS_INCREASE = "average_loss_increase"
    VOLATILITY_INCREASE = "volatility_increase"
    CORRELATION_BREAKDOWN = "correlation_breakdown"


class AlertAction(Enum):
    """Actions that can be triggered by alerts."""
    LOG_WARNING = "log_warning"
    SEND_EMAIL = "send_email"
    SEND_PUSH_NOTIFICATION = "send_push_notification"
    UPDATE_RECOMMENDATIONS = "update_recommendations"
    PAUSE_TRADING = "pause_trading"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    TRIGGER_EMERGENCY_STOP = "trigger_emergency_stop"


class NotificationChannel(Enum):
    """Available notification channels."""
    EMAIL = "email"
    SMS = "sms"
    PUSH_NOTIFICATION = "push_notification"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class DegradationTest:
    """Statistical test for performance degradation."""
    
    test_name: str
    test_function: Callable
    baseline_window: int  # Number of trades/days for baseline
    comparison_window: int  # Number of trades/days for comparison
    significance_threshold: float  # p-value threshold
    effect_size_threshold: float  # Minimum effect size to consider
    min_sample_size: int  # Minimum samples needed


@dataclass
class AlertRule:
    """Rule defining when and how to generate alerts."""
    
    rule_id: str
    name: str
    degradation_type: DegradationType
    severity_levels: Dict[str, float]  # threshold -> severity mapping
    actions: List[AlertAction]
    cooldown_minutes: int
    max_alerts_per_day: int
    enabled: bool = True
    
    # Conditions
    min_trades_required: int = 10
    lookback_periods: int = 5  # Number of periods to look back
    consecutive_violations: int = 1  # Violations needed to trigger
    
    # Notification settings
    notification_channels: List[NotificationChannel] = field(default_factory=list)
    notification_template: Optional[str] = None


@dataclass
class AlertEscalation:
    """Alert escalation configuration."""
    
    escalation_levels: List[Dict[str, Any]]  # Time -> actions
    auto_resolve_after_minutes: int = 60
    require_acknowledgment: bool = True
    escalate_unacknowledged_after_minutes: int = 30


@dataclass
class NotificationConfig:
    """Configuration for notification systems."""
    
    # Email settings
    email_enabled: bool = False
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    from_email: str = ""
    to_emails: List[str] = field(default_factory=list)
    
    # Push notification settings
    push_enabled: bool = False
    push_service_url: str = ""
    push_api_key: str = ""
    
    # Webhook settings
    webhook_enabled: bool = False
    webhook_urls: List[str] = field(default_factory=list)
    webhook_timeout_seconds: int = 10
    
    # Slack settings
    slack_enabled: bool = False
    slack_webhook_url: str = ""
    slack_channel: str = "#alerts"


class AlertsEngine:
    """
    Comprehensive alert engine for performance degradation detection.
    
    Provides statistical testing for performance changes, graduated alert system,
    automatic recommendation updates, and multi-channel notifications.
    """
    
    def __init__(self, db_session: Optional[Session] = None):
        """Initialize the alerts engine."""
        self.db_session = db_session or get_db_session()
        
        # Core services
        self.time_bin_analyzer = TimeBinAnalyzer(self.db_session)
        self.performance_calculator = PerformanceMetricsCalculator(self.db_session)
        self.recommendation_engine = RecommendationEngine(self.db_session)
        
        # Alert management
        self.alert_rules: Dict[str, AlertRule] = {}
        self.degradation_tests: Dict[str, DegradationTest] = {}
        self.active_alerts: Dict[str, MonitoringAlert] = {}
        self.alert_history: deque = deque(maxlen=10000)
        self.escalations: Dict[str, AlertEscalation] = {}
        
        # Notification system
        self.notification_config = NotificationConfig()
        self.notification_queue: deque = deque()
        
        # State tracking
        self.rule_violations: Dict[Tuple[str, TimeBin], List[datetime]] = defaultdict(list)
        self.alert_cooldowns: Dict[Tuple[str, TimeBin], datetime] = {}
        self.daily_alert_counts: Dict[Tuple[str, date], int] = defaultdict(int)
        
        # Performance data cache
        self.performance_cache: Dict[TimeBin, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Threading and async
        self.engine_task: Optional[asyncio.Task] = None
        self.notification_task: Optional[asyncio.Task] = None
        self.stop_event = Event()
        self.data_lock = Lock()
        
        # Callbacks
        self.alert_callbacks: List[Callable[[MonitoringAlert], None]] = []
        self.degradation_callbacks: List[Callable[[TimeBin, DegradationType, Dict], None]] = []
        
        # Initialize default tests and rules
        self._initialize_default_tests()
        self._initialize_default_rules()
        
        logger.info("AlertsEngine initialized")
    
    def _initialize_default_tests(self):
        """Initialize default degradation tests."""
        
        # Statistical significance test
        self.degradation_tests["t_test_performance"] = DegradationTest(
            test_name="Performance T-Test",
            test_function=self._t_test_performance_degradation,
            baseline_window=50,
            comparison_window=20,
            significance_threshold=0.05,
            effect_size_threshold=0.5,
            min_sample_size=15
        )
        
        # Win rate degradation test
        self.degradation_tests["win_rate_test"] = DegradationTest(
            test_name="Win Rate Proportion Test",
            test_function=self._proportion_test_win_rate,
            baseline_window=40,
            comparison_window=15,
            significance_threshold=0.05,
            effect_size_threshold=0.1,  # 10% difference
            min_sample_size=10
        )
        
        # Drawdown increase test
        self.degradation_tests["drawdown_test"] = DegradationTest(
            test_name="Maximum Drawdown Test",
            test_function=self._drawdown_increase_test,
            baseline_window=100,
            comparison_window=30,
            significance_threshold=0.05,
            effect_size_threshold=0.05,  # 5% increase
            min_sample_size=20
        )
        
        # Volatility increase test
        self.degradation_tests["volatility_test"] = DegradationTest(
            test_name="Volatility F-Test",
            test_function=self._f_test_volatility_increase,
            baseline_window=60,
            comparison_window=20,
            significance_threshold=0.05,
            effect_size_threshold=1.5,  # 50% variance increase
            min_sample_size=15
        )
    
    def _initialize_default_rules(self):
        """Initialize default alert rules."""
        
        # Critical performance degradation rule
        self.alert_rules["critical_performance"] = AlertRule(
            rule_id="critical_performance",
            name="Critical Performance Degradation",
            degradation_type=DegradationType.STATISTICAL_DEGRADATION,
            severity_levels={
                "warning": 0.05,
                "critical": 0.01,
                "emergency": 0.001
            },
            actions=[AlertAction.LOG_WARNING, AlertAction.SEND_EMAIL, AlertAction.UPDATE_RECOMMENDATIONS],
            cooldown_minutes=30,
            max_alerts_per_day=10,
            min_trades_required=20,
            lookback_periods=3,
            consecutive_violations=2,
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH_NOTIFICATION]
        )
        
        # Win rate decline rule
        self.alert_rules["win_rate_decline"] = AlertRule(
            rule_id="win_rate_decline",
            name="Win Rate Decline Alert",
            degradation_type=DegradationType.WIN_RATE_DECLINE,
            severity_levels={
                "warning": 0.15,  # 15% decline
                "critical": 0.25,  # 25% decline
                "emergency": 0.40   # 40% decline
            },
            actions=[AlertAction.LOG_WARNING, AlertAction.SEND_EMAIL],
            cooldown_minutes=60,
            max_alerts_per_day=5,
            min_trades_required=15,
            notification_channels=[NotificationChannel.EMAIL]
        )
        
        # Maximum drawdown rule
        self.alert_rules["max_drawdown"] = AlertRule(
            rule_id="max_drawdown",
            name="Maximum Drawdown Breach",
            degradation_type=DegradationType.MAXIMUM_DRAWDOWN_INCREASE,
            severity_levels={
                "warning": 0.15,   # 15% drawdown
                "critical": 0.20,  # 20% drawdown
                "emergency": 0.30   # 30% drawdown
            },
            actions=[AlertAction.LOG_WARNING, AlertAction.SEND_EMAIL, AlertAction.PAUSE_TRADING],
            cooldown_minutes=15,
            max_alerts_per_day=20,
            min_trades_required=10,
            consecutive_violations=1,  # Immediate alert
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH_NOTIFICATION]
        )
        
        # Consecutive losses rule
        self.alert_rules["consecutive_losses"] = AlertRule(
            rule_id="consecutive_losses",
            name="Consecutive Losses Alert",
            degradation_type=DegradationType.CONSECUTIVE_LOSSES,
            severity_levels={
                "warning": 5,      # 5 consecutive losses
                "critical": 8,     # 8 consecutive losses  
                "emergency": 12    # 12 consecutive losses
            },
            actions=[AlertAction.LOG_WARNING, AlertAction.SEND_EMAIL],
            cooldown_minutes=120,
            max_alerts_per_day=3,
            min_trades_required=5,
            notification_channels=[NotificationChannel.EMAIL]
        )
    
    def add_alert_rule(self, rule: AlertRule) -> bool:
        """Add a new alert rule."""
        try:
            with self.data_lock:
                self.alert_rules[rule.rule_id] = rule
            logger.info(f"Added alert rule: {rule.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add alert rule: {str(e)}")
            return False
    
    def remove_alert_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        try:
            with self.data_lock:
                if rule_id in self.alert_rules:
                    del self.alert_rules[rule_id]
                    logger.info(f"Removed alert rule: {rule_id}")
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to remove alert rule: {str(e)}")
            return False
    
    def configure_notifications(self, config: NotificationConfig):
        """Configure notification settings."""
        self.notification_config = config
        logger.info("Notification configuration updated")
    
    async def start_engine(self) -> bool:
        """Start the alerts engine."""
        try:
            self.stop_event.clear()
            
            # Start main engine task
            self.engine_task = asyncio.create_task(self._engine_loop())
            
            # Start notification processing task
            self.notification_task = asyncio.create_task(self._notification_loop())
            
            logger.info("AlertsEngine started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start alerts engine: {str(e)}")
            return False
    
    async def stop_engine(self) -> bool:
        """Stop the alerts engine."""
        try:
            self.stop_event.set()
            
            # Cancel tasks
            if self.engine_task:
                self.engine_task.cancel()
                try:
                    await self.engine_task
                except asyncio.CancelledError:
                    pass
                self.engine_task = None
            
            if self.notification_task:
                self.notification_task.cancel()
                try:
                    await self.notification_task
                except asyncio.CancelledError:
                    pass
                self.notification_task = None
            
            logger.info("AlertsEngine stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop alerts engine: {str(e)}")
            return False
    
    async def _engine_loop(self):
        """Main alert engine processing loop."""
        logger.info("Starting alerts engine loop")
        
        while not self.stop_event.is_set():
            try:
                # Process performance updates for all monitored time-bins
                await self._process_performance_updates()
                
                # Run degradation tests
                await self._run_degradation_tests()
                
                # Process alert escalations
                await self._process_alert_escalations()
                
                # Clean up old data
                await self._cleanup_old_data()
                
                # Wait before next cycle
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in alerts engine loop: {str(e)}")
                await asyncio.sleep(5)
        
        logger.info("Alerts engine loop stopped")
    
    async def _notification_loop(self):
        """Notification processing loop."""
        logger.info("Starting notification loop")
        
        while not self.stop_event.is_set():
            try:
                # Process notification queue
                while self.notification_queue:
                    notification = self.notification_queue.popleft()
                    await self._send_notification(notification)
                
                # Wait before checking again
                await asyncio.sleep(5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in notification loop: {str(e)}")
                await asyncio.sleep(5)
        
        logger.info("Notification loop stopped")
    
    async def process_performance_snapshot(self, time_bin: TimeBin, snapshot: PerformanceSnapshot):
        """Process a new performance snapshot for alert evaluation."""
        try:
            with self.data_lock:
                self.performance_cache[time_bin].append(snapshot)
            
            # Run immediate degradation checks for this time-bin
            await self._check_time_bin_degradation(time_bin)
            
        except Exception as e:
            logger.error(f"Error processing performance snapshot: {str(e)}")
    
    async def _process_performance_updates(self):
        """Process performance updates from monitoring service."""
        # This would typically integrate with TimeBinMonitoringService
        # For now, we'll check cached performance data
        pass
    
    async def _run_degradation_tests(self):
        """Run statistical degradation tests on all monitored time-bins."""
        with self.data_lock:
            time_bins_to_check = list(self.performance_cache.keys())
        
        for time_bin in time_bins_to_check:
            try:
                await self._check_time_bin_degradation(time_bin)
            except Exception as e:
                logger.error(f"Error checking degradation for {time_bin}: {str(e)}")
    
    async def _check_time_bin_degradation(self, time_bin: TimeBin):
        """Check for performance degradation in a specific time-bin."""
        with self.data_lock:
            snapshots = list(self.performance_cache[time_bin])
        
        if len(snapshots) < 10:
            return  # Not enough data
        
        # Run each degradation test
        for test_name, test in self.degradation_tests.items():
            try:
                result = await self._run_single_degradation_test(time_bin, snapshots, test)
                if result:
                    degradation_type, test_results = result
                    await self._process_degradation_result(time_bin, degradation_type, test_results)
            
            except Exception as e:
                logger.error(f"Error running test {test_name} for {time_bin}: {str(e)}")
    
    async def _run_single_degradation_test(
        self,
        time_bin: TimeBin,
        snapshots: List[PerformanceSnapshot],
        test: DegradationTest
    ) -> Optional[Tuple[DegradationType, Dict[str, Any]]]:
        """Run a single degradation test."""
        
        if len(snapshots) < test.min_sample_size:
            return None
        
        try:
            # Run the test function
            test_result = await test.test_function(snapshots, test)
            return test_result
            
        except Exception as e:
            logger.error(f"Error in degradation test {test.test_name}: {str(e)}")
            return None
    
    async def _t_test_performance_degradation(
        self,
        snapshots: List[PerformanceSnapshot],
        test: DegradationTest
    ) -> Optional[Tuple[DegradationType, Dict[str, Any]]]:
        """Test for statistical performance degradation using t-test."""
        
        if len(snapshots) < test.baseline_window:
            return None
        
        try:
            # Get recent and baseline performance
            recent_snapshots = snapshots[-test.comparison_window:]
            baseline_snapshots = snapshots[-(test.baseline_window + test.comparison_window):-test.comparison_window]
            
            if len(baseline_snapshots) < test.min_sample_size or len(recent_snapshots) < test.min_sample_size:
                return None
            
            # Extract average trade P&L
            recent_performance = [s.avg_trade_pnl for s in recent_snapshots]
            baseline_performance = [s.avg_trade_pnl for s in baseline_snapshots]
            
            # Perform two-sample t-test (recent < baseline indicates degradation)
            t_stat, p_value = stats.ttest_ind(recent_performance, baseline_performance, alternative='less')
            
            # Calculate effect size (Cohen's d)
            recent_mean = np.mean(recent_performance)
            baseline_mean = np.mean(baseline_performance)
            pooled_std = np.sqrt((np.var(recent_performance) + np.var(baseline_performance)) / 2)
            
            if pooled_std > 0:
                effect_size = (baseline_mean - recent_mean) / pooled_std
            else:
                effect_size = 0
            
            # Check if degradation is significant
            if p_value < test.significance_threshold and effect_size > test.effect_size_threshold:
                return DegradationType.STATISTICAL_DEGRADATION, {
                    'p_value': p_value,
                    'effect_size': effect_size,
                    't_statistic': t_stat,
                    'recent_mean': recent_mean,
                    'baseline_mean': baseline_mean,
                    'degradation_percentage': ((baseline_mean - recent_mean) / baseline_mean) * 100 if baseline_mean != 0 else 0
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in t-test performance degradation: {str(e)}")
            return None
    
    async def _proportion_test_win_rate(
        self,
        snapshots: List[PerformanceSnapshot], 
        test: DegradationTest
    ) -> Optional[Tuple[DegradationType, Dict[str, Any]]]:
        """Test for win rate degradation using proportion test."""
        
        if len(snapshots) < test.baseline_window:
            return None
        
        try:
            recent_snapshots = snapshots[-test.comparison_window:]
            baseline_snapshots = snapshots[-(test.baseline_window + test.comparison_window):-test.comparison_window]
            
            if len(baseline_snapshots) < test.min_sample_size or len(recent_snapshots) < test.min_sample_size:
                return None
            
            # Calculate win rates
            recent_win_rate = np.mean([s.win_rate for s in recent_snapshots])
            baseline_win_rate = np.mean([s.win_rate for s in baseline_snapshots])
            
            # Calculate total trades for each period
            recent_trades = sum(s.trades_count for s in recent_snapshots)
            baseline_trades = sum(s.trades_count for s in baseline_snapshots)
            
            if recent_trades < 10 or baseline_trades < 10:
                return None
            
            # Two-proportion z-test
            recent_wins = recent_win_rate * recent_trades
            baseline_wins = baseline_win_rate * baseline_trades
            
            total_wins = recent_wins + baseline_wins
            total_trades = recent_trades + baseline_trades
            pooled_proportion = total_wins / total_trades
            
            # Standard error
            se = np.sqrt(pooled_proportion * (1 - pooled_proportion) * (1/recent_trades + 1/baseline_trades))
            
            if se > 0:
                z_stat = (recent_win_rate - baseline_win_rate) / se
                p_value = stats.norm.cdf(z_stat)  # One-tailed test (degradation)
            else:
                return None
            
            # Effect size (difference in proportions)
            effect_size = baseline_win_rate - recent_win_rate
            
            if p_value < test.significance_threshold and effect_size > test.effect_size_threshold:
                return DegradationType.WIN_RATE_DECLINE, {
                    'p_value': p_value,
                    'effect_size': effect_size,
                    'z_statistic': z_stat,
                    'recent_win_rate': recent_win_rate,
                    'baseline_win_rate': baseline_win_rate,
                    'degradation_percentage': (effect_size / baseline_win_rate) * 100 if baseline_win_rate != 0 else 0
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in win rate proportion test: {str(e)}")
            return None
    
    async def _drawdown_increase_test(
        self,
        snapshots: List[PerformanceSnapshot],
        test: DegradationTest
    ) -> Optional[Tuple[DegradationType, Dict[str, Any]]]:
        """Test for maximum drawdown increase."""
        
        if len(snapshots) < test.baseline_window:
            return None
        
        try:
            recent_snapshots = snapshots[-test.comparison_window:]
            baseline_snapshots = snapshots[-(test.baseline_window + test.comparison_window):-test.comparison_window]
            
            if len(baseline_snapshots) < test.min_sample_size or len(recent_snapshots) < test.min_sample_size:
                return None
            
            # Get maximum drawdowns (absolute values)
            recent_drawdowns = [abs(s.max_drawdown) for s in recent_snapshots]
            baseline_drawdowns = [abs(s.max_drawdown) for s in baseline_snapshots]
            
            recent_max_dd = max(recent_drawdowns) if recent_drawdowns else 0
            baseline_max_dd = max(baseline_drawdowns) if baseline_drawdowns else 0
            
            # Test if recent drawdown is significantly worse
            drawdown_increase = recent_max_dd - baseline_max_dd
            
            # Simple threshold test (could be enhanced with more sophisticated statistics)
            if drawdown_increase > test.effect_size_threshold:
                return DegradationType.MAXIMUM_DRAWDOWN_INCREASE, {
                    'recent_max_drawdown': recent_max_dd,
                    'baseline_max_drawdown': baseline_max_dd,
                    'drawdown_increase': drawdown_increase,
                    'increase_percentage': (drawdown_increase / baseline_max_dd) * 100 if baseline_max_dd != 0 else float('inf')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in drawdown increase test: {str(e)}")
            return None
    
    async def _f_test_volatility_increase(
        self,
        snapshots: List[PerformanceSnapshot],
        test: DegradationTest
    ) -> Optional[Tuple[DegradationType, Dict[str, Any]]]:
        """Test for volatility increase using F-test."""
        
        if len(snapshots) < test.baseline_window:
            return None
        
        try:
            recent_snapshots = snapshots[-test.comparison_window:]
            baseline_snapshots = snapshots[-(test.baseline_window + test.comparison_window):-test.comparison_window]
            
            if len(baseline_snapshots) < test.min_sample_size or len(recent_snapshots) < test.min_sample_size:
                return None
            
            # Extract return series (using avg_trade_pnl as proxy)
            recent_returns = [s.avg_trade_pnl for s in recent_snapshots]
            baseline_returns = [s.avg_trade_pnl for s in baseline_snapshots]
            
            # Calculate variances
            recent_var = np.var(recent_returns, ddof=1)
            baseline_var = np.var(baseline_returns, ddof=1)
            
            if baseline_var == 0:
                return None
            
            # F-statistic for variance test
            f_stat = recent_var / baseline_var
            df1 = len(recent_returns) - 1
            df2 = len(baseline_returns) - 1
            
            # One-tailed p-value (testing if recent variance > baseline variance)
            p_value = 1 - stats.f.cdf(f_stat, df1, df2)
            
            if p_value < test.significance_threshold and f_stat > test.effect_size_threshold:
                return DegradationType.VOLATILITY_INCREASE, {
                    'p_value': p_value,
                    'f_statistic': f_stat,
                    'recent_volatility': np.sqrt(recent_var),
                    'baseline_volatility': np.sqrt(baseline_var),
                    'variance_ratio': f_stat,
                    'volatility_increase_percentage': ((np.sqrt(f_stat) - 1) * 100)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error in volatility F-test: {str(e)}")
            return None
    
    async def _process_degradation_result(
        self,
        time_bin: TimeBin,
        degradation_type: DegradationType,
        test_results: Dict[str, Any]
    ):
        """Process a detected degradation result."""
        
        # Find applicable alert rules
        applicable_rules = [
            rule for rule in self.alert_rules.values()
            if rule.enabled and rule.degradation_type == degradation_type
        ]
        
        for rule in applicable_rules:
            await self._evaluate_alert_rule(time_bin, rule, test_results)
        
        # Notify degradation callbacks
        for callback in self.degradation_callbacks:
            try:
                callback(time_bin, degradation_type, test_results)
            except Exception as e:
                logger.error(f"Error in degradation callback: {str(e)}")
    
    async def _evaluate_alert_rule(
        self,
        time_bin: TimeBin,
        rule: AlertRule,
        test_results: Dict[str, Any]
    ):
        """Evaluate whether an alert rule should be triggered."""
        
        try:
            # Check cooldown
            cooldown_key = (rule.rule_id, time_bin)
            if cooldown_key in self.alert_cooldowns:
                if datetime.now() < self.alert_cooldowns[cooldown_key]:
                    return  # Still in cooldown
            
            # Check daily limit
            today = datetime.now().date()
            daily_key = (rule.rule_id, today)
            if self.daily_alert_counts[daily_key] >= rule.max_alerts_per_day:
                return  # Daily limit reached
            
            # Determine severity based on test results
            severity = self._determine_rule_severity(rule, test_results)
            if not severity:
                return  # No severity threshold met
            
            # Check for consecutive violations if required
            violation_key = (rule.rule_id, time_bin)
            current_time = datetime.now()
            self.rule_violations[violation_key].append(current_time)
            
            # Keep only recent violations
            lookback_time = current_time - timedelta(hours=1)
            self.rule_violations[violation_key] = [
                t for t in self.rule_violations[violation_key]
                if t >= lookback_time
            ]
            
            # Check if we have enough consecutive violations
            if len(self.rule_violations[violation_key]) < rule.consecutive_violations:
                return
            
            # Generate alert
            alert = await self._generate_degradation_alert(time_bin, rule, severity, test_results)
            
            if alert:
                # Store alert
                with self.data_lock:
                    self.active_alerts[alert.alert_id] = alert
                    self.alert_history.append(alert)
                
                # Set cooldown
                self.alert_cooldowns[cooldown_key] = current_time + timedelta(minutes=rule.cooldown_minutes)
                
                # Update daily count
                self.daily_alert_counts[daily_key] += 1
                
                # Execute alert actions
                await self._execute_alert_actions(alert, rule)
                
                # Notify callbacks
                for callback in self.alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as e:
                        logger.error(f"Error in alert callback: {str(e)}")
                
                logger.warning(f"Generated degradation alert: {alert.message}")
        
        except Exception as e:
            logger.error(f"Error evaluating alert rule {rule.rule_id}: {str(e)}")
    
    def _determine_rule_severity(self, rule: AlertRule, test_results: Dict[str, Any]) -> Optional[AlertSeverity]:
        """Determine alert severity based on rule thresholds and test results."""
        
        # Get the primary metric for comparison
        metric_value = None
        if 'p_value' in test_results:
            metric_value = test_results['p_value']
        elif 'degradation_percentage' in test_results:
            metric_value = abs(test_results['degradation_percentage']) / 100
        elif 'recent_max_drawdown' in test_results:
            metric_value = test_results['recent_max_drawdown']
        elif 'consecutive_losses' in test_results:
            metric_value = test_results['consecutive_losses']
        
        if metric_value is None:
            return None
        
        # Check thresholds in order of severity
        if 'emergency' in rule.severity_levels:
            if (rule.degradation_type == DegradationType.STATISTICAL_DEGRADATION and 
                metric_value <= rule.severity_levels['emergency']):
                return AlertSeverity.EMERGENCY
            elif (rule.degradation_type != DegradationType.STATISTICAL_DEGRADATION and
                  metric_value >= rule.severity_levels['emergency']):
                return AlertSeverity.EMERGENCY
        
        if 'critical' in rule.severity_levels:
            if (rule.degradation_type == DegradationType.STATISTICAL_DEGRADATION and 
                metric_value <= rule.severity_levels['critical']):
                return AlertSeverity.CRITICAL
            elif (rule.degradation_type != DegradationType.STATISTICAL_DEGRADATION and
                  metric_value >= rule.severity_levels['critical']):
                return AlertSeverity.CRITICAL
        
        if 'warning' in rule.severity_levels:
            if (rule.degradation_type == DegradationType.STATISTICAL_DEGRADATION and 
                metric_value <= rule.severity_levels['warning']):
                return AlertSeverity.WARNING
            elif (rule.degradation_type != DegradationType.STATISTICAL_DEGRADATION and
                  metric_value >= rule.severity_levels['warning']):
                return AlertSeverity.WARNING
        
        return None
    
    async def _generate_degradation_alert(
        self,
        time_bin: TimeBin,
        rule: AlertRule,
        severity: AlertSeverity,
        test_results: Dict[str, Any]
    ) -> Optional[MonitoringAlert]:
        """Generate a degradation alert."""
        
        try:
            alert_id = f"deg_{int(datetime.now().timestamp())}_{rule.rule_id}"
            
            # Generate message
            message = self._generate_degradation_message(time_bin, rule, severity, test_results)
            
            alert = MonitoringAlert(
                alert_id=alert_id,
                timestamp=datetime.now(),
                time_bin=time_bin,
                alert_type=AnomalyType.PERFORMANCE_DEGRADATION,  # Map to existing type
                severity=severity,
                message=message,
                data={
                    'rule_id': rule.rule_id,
                    'degradation_type': rule.degradation_type.value,
                    'test_results': test_results,
                    'rule_name': rule.name
                }
            )
            
            return alert
            
        except Exception as e:
            logger.error(f"Error generating degradation alert: {str(e)}")
            return None
    
    def _generate_degradation_message(
        self,
        time_bin: TimeBin,
        rule: AlertRule,
        severity: AlertSeverity,
        test_results: Dict[str, Any]
    ) -> str:
        """Generate human-readable degradation alert message."""
        
        time_bin_str = f"{time_bin.account_name}:{time_bin.hour}:{time_bin.minute_bin:02d}"
        
        if rule.degradation_type == DegradationType.STATISTICAL_DEGRADATION:
            return (f"{severity.value.upper()}: Statistical performance degradation detected for {time_bin_str}. "
                   f"P-value: {test_results.get('p_value', 0):.4f}, "
                   f"Effect size: {test_results.get('effect_size', 0):.2f}, "
                   f"Performance decline: {test_results.get('degradation_percentage', 0):.1f}%")
        
        elif rule.degradation_type == DegradationType.WIN_RATE_DECLINE:
            return (f"{severity.value.upper()}: Win rate decline detected for {time_bin_str}. "
                   f"Current: {test_results.get('recent_win_rate', 0):.1%}, "
                   f"Baseline: {test_results.get('baseline_win_rate', 0):.1%}, "
                   f"Decline: {test_results.get('degradation_percentage', 0):.1f}%")
        
        elif rule.degradation_type == DegradationType.MAXIMUM_DRAWDOWN_INCREASE:
            return (f"{severity.value.upper()}: Maximum drawdown increased for {time_bin_str}. "
                   f"Current: {test_results.get('recent_max_drawdown', 0):.1%}, "
                   f"Increase: {test_results.get('drawdown_increase', 0):.1%}")
        
        elif rule.degradation_type == DegradationType.VOLATILITY_INCREASE:
            return (f"{severity.value.upper()}: Volatility increase detected for {time_bin_str}. "
                   f"Increase: {test_results.get('volatility_increase_percentage', 0):.1f}%, "
                   f"Variance ratio: {test_results.get('variance_ratio', 1):.2f}")
        
        else:
            return f"{severity.value.upper()}: {rule.name} triggered for {time_bin_str}"
    
    async def _execute_alert_actions(self, alert: MonitoringAlert, rule: AlertRule):
        """Execute actions specified by the alert rule."""
        
        for action in rule.actions:
            try:
                if action == AlertAction.LOG_WARNING:
                    logger.warning(f"Alert Action - {alert.message}")
                
                elif action == AlertAction.SEND_EMAIL:
                    await self._queue_email_notification(alert, rule)
                
                elif action == AlertAction.SEND_PUSH_NOTIFICATION:
                    await self._queue_push_notification(alert, rule)
                
                elif action == AlertAction.UPDATE_RECOMMENDATIONS:
                    await self._update_recommendations_for_degradation(alert)
                
                elif action == AlertAction.PAUSE_TRADING:
                    await self._pause_trading_for_time_bin(alert.time_bin, alert)
                
                elif action == AlertAction.ESCALATE_TO_HUMAN:
                    await self._escalate_to_human(alert)
                
                elif action == AlertAction.TRIGGER_EMERGENCY_STOP:
                    await self._trigger_emergency_stop(alert)
            
            except Exception as e:
                logger.error(f"Error executing alert action {action}: {str(e)}")
    
    async def _queue_email_notification(self, alert: MonitoringAlert, rule: AlertRule):
        """Queue email notification."""
        if self.notification_config.email_enabled:
            notification = {
                'type': 'email',
                'alert': alert,
                'rule': rule,
                'timestamp': datetime.now()
            }
            self.notification_queue.append(notification)
    
    async def _queue_push_notification(self, alert: MonitoringAlert, rule: AlertRule):
        """Queue push notification."""
        if self.notification_config.push_enabled:
            notification = {
                'type': 'push',
                'alert': alert,
                'rule': rule,
                'timestamp': datetime.now()
            }
            self.notification_queue.append(notification)
    
    async def _update_recommendations_for_degradation(self, alert: MonitoringAlert):
        """Update recommendations based on performance degradation."""
        try:
            # Reduce confidence or disable recommendations for degraded time-bin
            time_bin = alert.time_bin
            
            # This would integrate with the RecommendationEngine
            # For now, just log the action
            logger.info(f"Updating recommendations due to degradation in {time_bin}")
            
        except Exception as e:
            logger.error(f"Error updating recommendations: {str(e)}")
    
    async def _pause_trading_for_time_bin(self, time_bin: TimeBin, alert: MonitoringAlert):
        """Pause trading for a specific time-bin."""
        try:
            # This would integrate with trading execution system
            logger.warning(f"TRADING PAUSED for {time_bin} due to {alert.alert_type}")
            
        except Exception as e:
            logger.error(f"Error pausing trading: {str(e)}")
    
    async def _escalate_to_human(self, alert: MonitoringAlert):
        """Escalate alert to human operator."""
        try:
            # This would integrate with escalation system
            logger.critical(f"HUMAN ESCALATION: {alert.message}")
            
        except Exception as e:
            logger.error(f"Error escalating to human: {str(e)}")
    
    async def _trigger_emergency_stop(self, alert: MonitoringAlert):
        """Trigger emergency stop procedures."""
        try:
            # This would integrate with emergency stop system
            logger.critical(f"EMERGENCY STOP TRIGGERED: {alert.message}")
            
        except Exception as e:
            logger.error(f"Error triggering emergency stop: {str(e)}")
    
    async def _send_notification(self, notification: Dict[str, Any]):
        """Send a queued notification."""
        try:
            notification_type = notification['type']
            alert = notification['alert']
            
            if notification_type == 'email':
                await self._send_email_notification(alert)
            elif notification_type == 'push':
                await self._send_push_notification(alert)
            elif notification_type == 'webhook':
                await self._send_webhook_notification(alert)
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
    
    async def _send_email_notification(self, alert: MonitoringAlert):
        """Send email notification."""
        if not self.notification_config.email_enabled or not self.notification_config.to_emails:
            return
        
        try:
            # Create email message
            msg = MimeMultipart()
            msg['From'] = self.notification_config.from_email
            msg['To'] = ', '.join(self.notification_config.to_emails)
            msg['Subject'] = f"Trading Alert: {alert.severity.value.title()} - {alert.alert_type.value}"
            
            # Email body
            body = f"""
            Trading Alert Notification
            
            Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            Severity: {alert.severity.value.upper()}
            Time-Bin: {alert.time_bin.account_name}:{alert.time_bin.hour}:{alert.time_bin.minute_bin:02d}
            Alert Type: {alert.alert_type.value}
            
            Message: {alert.message}
            
            Alert ID: {alert.alert_id}
            
            This is an automated message from the Trading Platform Alert System.
            """
            
            msg.attach(MimeText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.notification_config.smtp_server, self.notification_config.smtp_port)
            server.starttls()
            server.login(self.notification_config.smtp_username, self.notification_config.smtp_password)
            
            text = msg.as_string()
            server.sendmail(self.notification_config.from_email, self.notification_config.to_emails, text)
            server.quit()
            
            logger.info(f"Email notification sent for alert {alert.alert_id}")
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {str(e)}")
    
    async def _send_push_notification(self, alert: MonitoringAlert):
        """Send push notification."""
        # Implementation would depend on push notification service
        logger.info(f"Push notification queued for alert {alert.alert_id}")
    
    async def _send_webhook_notification(self, alert: MonitoringAlert):
        """Send webhook notification."""
        # Implementation would use HTTP requests to webhook URLs
        logger.info(f"Webhook notification queued for alert {alert.alert_id}")
    
    async def _process_alert_escalations(self):
        """Process alert escalations for unacknowledged alerts."""
        current_time = datetime.now()
        
        with self.data_lock:
            alerts_to_escalate = [
                alert for alert in self.active_alerts.values()
                if (not alert.is_acknowledged and
                    current_time - alert.timestamp > timedelta(minutes=30) and
                    alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY])
            ]
        
        for alert in alerts_to_escalate:
            try:
                await self._escalate_to_human(alert)
                alert.is_acknowledged = True  # Prevent re-escalation
                alert.acknowledged_by = "auto_escalation"
                alert.acknowledged_at = current_time
            except Exception as e:
                logger.error(f"Error processing escalation for alert {alert.alert_id}: {str(e)}")
    
    async def _cleanup_old_data(self):
        """Clean up old alerts and violation data."""
        current_time = datetime.now()
        
        with self.data_lock:
            # Clean up old alerts (keep for 7 days)
            cutoff_time = current_time - timedelta(days=7)
            alerts_to_remove = [
                alert_id for alert_id, alert in self.active_alerts.items()
                if alert.timestamp < cutoff_time
            ]
            
            for alert_id in alerts_to_remove:
                del self.active_alerts[alert_id]
            
            # Clean up old violation data
            violation_cutoff = current_time - timedelta(hours=24)
            for key in list(self.rule_violations.keys()):
                self.rule_violations[key] = [
                    t for t in self.rule_violations[key]
                    if t >= violation_cutoff
                ]
                if not self.rule_violations[key]:
                    del self.rule_violations[key]
            
            # Clean up old daily counts
            today = current_time.date()
            old_dates = [
                date_key for date_key in self.daily_alert_counts.keys()
                if (today - date_key[1]).days > 7
            ]
            for date_key in old_dates:
                del self.daily_alert_counts[date_key]
    
    # Public interface methods
    
    def add_alert_callback(self, callback: Callable[[MonitoringAlert], None]):
        """Add callback for alert notifications."""
        self.alert_callbacks.append(callback)
    
    def add_degradation_callback(self, callback: Callable[[TimeBin, DegradationType, Dict], None]):
        """Add callback for degradation detection."""
        self.degradation_callbacks.append(callback)
    
    def get_active_alerts(self, time_bin: Optional[TimeBin] = None) -> List[MonitoringAlert]:
        """Get active alerts, optionally filtered by time-bin."""
        with self.data_lock:
            if time_bin:
                return [alert for alert in self.active_alerts.values() if alert.time_bin == time_bin]
            else:
                return list(self.active_alerts.values())
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "user") -> bool:
        """Acknowledge an alert."""
        try:
            with self.data_lock:
                if alert_id in self.active_alerts:
                    alert = self.active_alerts[alert_id]
                    alert.is_acknowledged = True
                    alert.acknowledged_at = datetime.now()
                    alert.acknowledged_by = acknowledged_by
                    return True
                return False
        except Exception as e:
            logger.error(f"Error acknowledging alert: {str(e)}")
            return False
    
    def get_engine_status(self) -> Dict[str, Any]:
        """Get the current status of the alerts engine."""
        with self.data_lock:
            return {
                'running': self.engine_task is not None and not self.engine_task.done(),
                'active_alerts': len(self.active_alerts),
                'total_rules': len(self.alert_rules),
                'enabled_rules': len([r for r in self.alert_rules.values() if r.enabled]),
                'notification_queue_size': len(self.notification_queue),
                'notification_channels_configured': sum([
                    self.notification_config.email_enabled,
                    self.notification_config.push_enabled,
                    self.notification_config.webhook_enabled,
                    self.notification_config.slack_enabled
                ])
            }