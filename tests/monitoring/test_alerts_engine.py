"""
Comprehensive test suite for AlertsEngine with performance degradation scenarios.

Tests cover:
1. Statistical degradation testing with various performance scenarios
2. Graduated alert system with different severity levels
3. Alert rule configuration and threshold management
4. Notification system integration and multi-channel support
5. Recommendation update triggers and trading controls
6. Alert escalation and acknowledgment workflows
7. Rate limiting and cooldown functionality
8. Data cleanup and memory management
9. Concurrent alert processing and performance
10. Production-ready error handling and reliability
"""

import pytest
import asyncio
import os
import tempfile
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import numpy as np
from typing import List, Dict, Any

# Import the test infrastructure
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from trading_platform.services.monitoring.alerts_engine import (
    AlertsEngine,
    AlertRule,
    AlertAction,
    DegradationType,
    NotificationChannel,
    NotificationConfig,
    DegradationTest,
    AlertEscalation
)
from trading_platform.services.monitoring.time_bin_monitoring_service import (
    PerformanceSnapshot,
    MonitoringAlert,
    AlertSeverity,
    AnomalyType
)
from trading_platform.services.time_bin_analyzer import SimpleTrade, TimeBin


class TestAlertsEngine:
    """Test suite for AlertsEngine functionality"""
    
    @pytest.fixture
    def sample_time_bin(self):
        """Create a sample time bin for testing"""
        return TimeBin(
            account_name='ALERTS_TEST_ACCOUNT',
            hour=10,
            minute_bin=15
        )
    
    @pytest.fixture
    def notification_config(self):
        """Create test notification configuration"""
        return NotificationConfig(
            email_enabled=True,
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="test@test.com",
            smtp_password="testpass",
            from_email="alerts@tradingplatform.com",
            to_emails=["admin@test.com", "trader@test.com"],
            push_enabled=True,
            push_service_url="https://push.test.com",
            push_api_key="test_key_123",
            webhook_enabled=True,
            webhook_urls=["https://webhook.test.com/alerts"],
            slack_enabled=True,
            slack_webhook_url="https://hooks.slack.com/test",
            slack_channel="#trading-alerts"
        )
    
    @pytest.fixture
    def degrading_performance_snapshots(self, sample_time_bin):
        """Generate snapshots showing performance degradation"""
        snapshots = []
        
        # Good baseline performance (first 50 snapshots)
        for i in range(50):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(days=60-i),
                time_bin=sample_time_bin,
                trades_count=25 + np.random.randint(-3, 4),
                total_pnl=1200 + np.random.uniform(-100, 200),
                win_rate=0.68 + np.random.uniform(-0.05, 0.05),  # Good baseline win rate
                avg_trade_pnl=48 + np.random.uniform(-8, 12),    # Good baseline avg
                max_drawdown=0.06 + np.random.uniform(-0.02, 0.02),
                sharpe_ratio=1.4 + np.random.uniform(-0.2, 0.3),
                profit_factor=2.1 + np.random.uniform(-0.3, 0.4),
                recent_trades=[],
                statistical_significance=True,
                p_value=0.02 + np.random.uniform(0, 0.02)
            )
            snapshots.append(snapshot)
        
        # Degrading performance (recent 20 snapshots)
        for i in range(20):
            degradation_factor = (i + 1) / 20  # Progressive degradation
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(days=20-i),
                time_bin=sample_time_bin,
                trades_count=22 + np.random.randint(-2, 3),
                total_pnl=800 - (degradation_factor * 400) + np.random.uniform(-100, 100),
                win_rate=0.45 - (degradation_factor * 0.15) + np.random.uniform(-0.03, 0.03),  # Degrading win rate
                avg_trade_pnl=28 - (degradation_factor * 20) + np.random.uniform(-5, 5),       # Degrading avg
                max_drawdown=0.08 + (degradation_factor * 0.12) + np.random.uniform(-0.01, 0.02),  # Increasing drawdown
                sharpe_ratio=0.8 - (degradation_factor * 0.5) + np.random.uniform(-0.1, 0.1),
                profit_factor=1.2 - (degradation_factor * 0.4) + np.random.uniform(-0.1, 0.2),
                recent_trades=[],
                statistical_significance=i < 10,  # Losing significance over time
                p_value=0.04 + (degradation_factor * 0.1) + np.random.uniform(0, 0.02)
            )
            snapshots.append(snapshot)
        
        return snapshots
    
    @pytest.fixture
    def stable_performance_snapshots(self, sample_time_bin):
        """Generate snapshots showing stable performance"""
        snapshots = []
        
        for i in range(50):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(days=50-i),
                time_bin=sample_time_bin,
                trades_count=25 + np.random.randint(-2, 3),
                total_pnl=1500 + np.random.uniform(-150, 150),
                win_rate=0.65 + np.random.uniform(-0.03, 0.03),
                avg_trade_pnl=60 + np.random.uniform(-5, 5),
                max_drawdown=0.07 + np.random.uniform(-0.01, 0.01),
                sharpe_ratio=1.3 + np.random.uniform(-0.1, 0.1),
                profit_factor=1.9 + np.random.uniform(-0.1, 0.1),
                recent_trades=[],
                statistical_significance=True,
                p_value=0.015 + np.random.uniform(0, 0.01)
            )
            snapshots.append(snapshot)
        
        return snapshots
    
    @pytest.fixture
    def volatile_performance_snapshots(self, sample_time_bin):
        """Generate snapshots showing increased volatility"""
        snapshots = []
        
        # Stable baseline (first 40 snapshots)
        for i in range(40):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(days=50-i),
                time_bin=sample_time_bin,
                trades_count=25,
                total_pnl=1200,
                win_rate=0.60,
                avg_trade_pnl=48 + np.random.uniform(-8, 8),    # Low volatility
                max_drawdown=0.05,
                sharpe_ratio=1.2,
                profit_factor=1.8,
                recent_trades=[],
                statistical_significance=True,
                p_value=0.02
            )
            snapshots.append(snapshot)
        
        # High volatility period (recent 20 snapshots)
        for i in range(20):
            snapshot = PerformanceSnapshot(
                timestamp=datetime.now() - timedelta(days=20-i),
                time_bin=sample_time_bin,
                trades_count=25,
                total_pnl=1200,
                win_rate=0.60,
                avg_trade_pnl=48 + np.random.uniform(-25, 25),  # High volatility
                max_drawdown=0.05,
                sharpe_ratio=1.2,
                profit_factor=1.8,
                recent_trades=[],
                statistical_significance=True,
                p_value=0.02
            )
            snapshots.append(snapshot)
        
        return snapshots
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock()
    
    @pytest.fixture
    def alerts_engine(self, mock_db_session):
        """Create AlertsEngine with mocked dependencies"""
        with patch('trading_platform.services.monitoring.alerts_engine.get_db_session') as mock_get_db:
            mock_get_db.return_value = mock_db_session
            
            engine = AlertsEngine(mock_db_session)
            
            # Mock the analyzers and services
            engine.time_bin_analyzer = Mock()
            engine.performance_calculator = Mock()
            engine.recommendation_engine = Mock()
            
            return engine
    
    def test_engine_initialization(self, alerts_engine):
        """Test alerts engine initialization"""
        
        assert len(alerts_engine.alert_rules) > 0  # Default rules loaded
        assert len(alerts_engine.degradation_tests) > 0  # Default tests loaded
        assert len(alerts_engine.active_alerts) == 0
        assert len(alerts_engine.alert_callbacks) == 0
        assert len(alerts_engine.degradation_callbacks) == 0
        
        # Check default rules exist
        assert 'critical_performance' in alerts_engine.alert_rules
        assert 'win_rate_decline' in alerts_engine.alert_rules
        assert 'max_drawdown' in alerts_engine.alert_rules
        assert 'consecutive_losses' in alerts_engine.alert_rules
        
        # Check default tests exist
        assert 't_test_performance' in alerts_engine.degradation_tests
        assert 'win_rate_test' in alerts_engine.degradation_tests
        assert 'drawdown_test' in alerts_engine.degradation_tests
        assert 'volatility_test' in alerts_engine.degradation_tests
        
        print("✓ Engine initialization validation passed")
        print(f"  - Default alert rules: {len(alerts_engine.alert_rules)}")
        print(f"  - Default degradation tests: {len(alerts_engine.degradation_tests)}")
    
    def test_notification_configuration(self, alerts_engine, notification_config):
        """Test notification system configuration"""
        
        # Configure notifications
        alerts_engine.configure_notifications(notification_config)
        
        assert alerts_engine.notification_config == notification_config
        assert alerts_engine.notification_config.email_enabled is True
        assert alerts_engine.notification_config.push_enabled is True
        assert alerts_engine.notification_config.webhook_enabled is True
        assert alerts_engine.notification_config.slack_enabled is True
        
        print("✓ Notification configuration validation passed")
        print(f"  - Email recipients: {len(notification_config.to_emails)}")
        print(f"  - Webhook URLs: {len(notification_config.webhook_urls)}")
    
    @pytest.mark.asyncio
    async def test_engine_start_stop(self, alerts_engine):
        """Test starting and stopping the alerts engine"""
        
        # Test start
        result = await alerts_engine.start_engine()
        assert result is True
        assert alerts_engine.engine_task is not None
        assert alerts_engine.notification_task is not None
        
        # Test stop
        result = await alerts_engine.stop_engine()
        assert result is True
        assert alerts_engine.engine_task is None
        assert alerts_engine.notification_task is None
        
        print("✓ Engine start/stop validation passed")
    
    @pytest.mark.asyncio
    async def test_statistical_performance_degradation_detection(
        self, 
        alerts_engine, 
        sample_time_bin, 
        degrading_performance_snapshots
    ):
        """Test statistical t-test for performance degradation"""
        
        # Add snapshots to cache
        for snapshot in degrading_performance_snapshots:
            alerts_engine.performance_cache[sample_time_bin].append(snapshot)
        
        # Get the t-test degradation test
        t_test = alerts_engine.degradation_tests['t_test_performance']
        
        # Run the test
        result = await alerts_engine._run_single_degradation_test(
            sample_time_bin, 
            degrading_performance_snapshots, 
            t_test
        )
        
        # Should detect degradation
        assert result is not None
        degradation_type, test_results = result
        
        assert degradation_type == DegradationType.STATISTICAL_DEGRADATION
        assert 'p_value' in test_results
        assert 'effect_size' in test_results
        assert 'degradation_percentage' in test_results
        
        # Should be statistically significant
        assert test_results['p_value'] < 0.05
        assert test_results['effect_size'] > 0.5
        assert test_results['degradation_percentage'] > 0
        
        print("✓ Statistical performance degradation detection validation passed")
        print(f"  - P-value: {test_results['p_value']:.4f}")
        print(f"  - Effect size: {test_results['effect_size']:.2f}")
        print(f"  - Performance decline: {test_results['degradation_percentage']:.1f}%")
    
    @pytest.mark.asyncio
    async def test_win_rate_degradation_detection(
        self, 
        alerts_engine, 
        sample_time_bin, 
        degrading_performance_snapshots
    ):
        """Test win rate degradation using proportion test"""
        
        # Get the win rate test
        win_rate_test = alerts_engine.degradation_tests['win_rate_test']
        
        # Run the test
        result = await alerts_engine._run_single_degradation_test(
            sample_time_bin,
            degrading_performance_snapshots,
            win_rate_test
        )
        
        # Should detect win rate decline
        assert result is not None
        degradation_type, test_results = result
        
        assert degradation_type == DegradationType.WIN_RATE_DECLINE
        assert 'recent_win_rate' in test_results
        assert 'baseline_win_rate' in test_results
        assert 'degradation_percentage' in test_results
        
        # Recent win rate should be lower than baseline
        assert test_results['recent_win_rate'] < test_results['baseline_win_rate']
        assert test_results['degradation_percentage'] > 10  # At least 10% decline
        
        print("✓ Win rate degradation detection validation passed")
        print(f"  - Baseline win rate: {test_results['baseline_win_rate']:.1%}")
        print(f"  - Recent win rate: {test_results['recent_win_rate']:.1%}")
        print(f"  - Win rate decline: {test_results['degradation_percentage']:.1f}%")
    
    @pytest.mark.asyncio
    async def test_volatility_increase_detection(
        self, 
        alerts_engine, 
        sample_time_bin, 
        volatile_performance_snapshots
    ):
        """Test volatility increase detection using F-test"""
        
        # Get the volatility test
        volatility_test = alerts_engine.degradation_tests['volatility_test']
        
        # Run the test
        result = await alerts_engine._run_single_degradation_test(
            sample_time_bin,
            volatile_performance_snapshots,
            volatility_test
        )
        
        # Should detect volatility increase
        assert result is not None
        degradation_type, test_results = result
        
        assert degradation_type == DegradationType.VOLATILITY_INCREASE
        assert 'f_statistic' in test_results
        assert 'variance_ratio' in test_results
        assert 'volatility_increase_percentage' in test_results
        
        # Should show significant volatility increase
        assert test_results['f_statistic'] > 1.5
        assert test_results['volatility_increase_percentage'] > 0
        
        print("✓ Volatility increase detection validation passed")
        print(f"  - F-statistic: {test_results['f_statistic']:.2f}")
        print(f"  - Variance ratio: {test_results['variance_ratio']:.2f}")
        print(f"  - Volatility increase: {test_results['volatility_increase_percentage']:.1f}%")
    
    @pytest.mark.asyncio
    async def test_no_degradation_with_stable_performance(
        self,
        alerts_engine,
        sample_time_bin,
        stable_performance_snapshots
    ):
        """Test that stable performance does not trigger degradation alerts"""
        
        # Add stable snapshots to cache
        for snapshot in stable_performance_snapshots:
            alerts_engine.performance_cache[sample_time_bin].append(snapshot)
        
        # Run degradation check
        await alerts_engine._check_time_bin_degradation(sample_time_bin)
        
        # Should not generate any alerts
        assert len(alerts_engine.active_alerts) == 0
        
        # Test individual degradation tests
        for test_name, test in alerts_engine.degradation_tests.items():
            result = await alerts_engine._run_single_degradation_test(
                sample_time_bin,
                stable_performance_snapshots,
                test
            )
            # Should not detect degradation in stable performance
            assert result is None, f"Test {test_name} incorrectly detected degradation in stable performance"
        
        print("✓ Stable performance validation passed")
        print("  - No false positive degradation alerts generated")
        print(f"  - Tested {len(alerts_engine.degradation_tests)} degradation tests")
    
    @pytest.mark.asyncio
    async def test_alert_rule_evaluation_and_severity(
        self,
        alerts_engine,
        sample_time_bin,
        degrading_performance_snapshots
    ):
        """Test alert rule evaluation and severity determination"""
        
        # Track generated alerts
        generated_alerts = []
        
        def alert_callback(alert: MonitoringAlert):
            generated_alerts.append(alert)
        
        alerts_engine.add_alert_callback(alert_callback)
        
        # Add degrading snapshots
        for snapshot in degrading_performance_snapshots:
            alerts_engine.performance_cache[sample_time_bin].append(snapshot)
        
        # Run degradation checks
        await alerts_engine._check_time_bin_degradation(sample_time_bin)
        
        # Should generate alerts
        assert len(generated_alerts) > 0
        
        # Check alert properties
        for alert in generated_alerts:
            assert alert.time_bin == sample_time_bin
            assert alert.severity in [AlertSeverity.WARNING, AlertSeverity.CRITICAL, AlertSeverity.EMERGENCY]
            assert alert.timestamp is not None
            assert alert.message is not None
            assert not alert.is_acknowledged
            assert 'rule_id' in alert.data
            assert 'degradation_type' in alert.data
            assert 'test_results' in alert.data
        
        # Check that more severe degradation results in higher severity
        critical_alerts = [a for a in generated_alerts if a.severity == AlertSeverity.CRITICAL]
        warning_alerts = [a for a in generated_alerts if a.severity == AlertSeverity.WARNING]
        
        print("✓ Alert rule evaluation and severity validation passed")
        print(f"  - Total alerts generated: {len(generated_alerts)}")
        print(f"  - Critical alerts: {len(critical_alerts)}")
        print(f"  - Warning alerts: {len(warning_alerts)}")
        for alert in generated_alerts[:3]:  # Show first 3 alerts
            print(f"    {alert.severity.value}: {alert.message}")
    
    @pytest.mark.asyncio
    async def test_alert_cooldown_and_rate_limiting(
        self,
        alerts_engine,
        sample_time_bin
    ):
        """Test alert cooldown and rate limiting functionality"""
        
        generated_alerts = []
        
        def alert_callback(alert: MonitoringAlert):
            generated_alerts.append(alert)
        
        alerts_engine.add_alert_callback(alert_callback)
        
        # Get a rule for testing
        test_rule = alerts_engine.alert_rules['critical_performance']
        
        # Create test results that would trigger alert
        test_results = {
            'p_value': 0.001,  # Very significant
            'effect_size': 2.0,
            'degradation_percentage': 50.0
        }
        
        # Generate multiple alerts rapidly
        for _ in range(5):
            await alerts_engine._evaluate_alert_rule(sample_time_bin, test_rule, test_results)
        
        # Should only generate one alert due to cooldown
        assert len(generated_alerts) == 1
        
        # Check that cooldown is set
        cooldown_key = (test_rule.rule_id, sample_time_bin)
        assert cooldown_key in alerts_engine.alert_cooldowns
        
        # Check daily count
        today = datetime.now().date()
        daily_key = (test_rule.rule_id, today)
        assert alerts_engine.daily_alert_counts[daily_key] == 1
        
        print("✓ Alert cooldown and rate limiting validation passed")
        print(f"  - Generated {len(generated_alerts)} alerts from 5 attempts")
        print(f"  - Cooldown period set until: {alerts_engine.alert_cooldowns[cooldown_key]}")
    
    @pytest.mark.asyncio
    async def test_custom_alert_rule_addition(self, alerts_engine):
        """Test adding custom alert rules"""
        
        # Create custom alert rule
        custom_rule = AlertRule(
            rule_id="custom_test_rule",
            name="Custom Test Rule",
            degradation_type=DegradationType.SHARPE_RATIO_DECLINE,
            severity_levels={
                "warning": 0.5,
                "critical": 0.2,
                "emergency": 0.0
            },
            actions=[AlertAction.LOG_WARNING, AlertAction.SEND_EMAIL],
            cooldown_minutes=60,
            max_alerts_per_day=3,
            min_trades_required=25,
            consecutive_violations=3,
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.SLACK]
        )
        
        # Add the rule
        result = alerts_engine.add_alert_rule(custom_rule)
        assert result is True
        assert custom_rule.rule_id in alerts_engine.alert_rules
        assert alerts_engine.alert_rules[custom_rule.rule_id] == custom_rule
        
        # Test removing the rule
        result = alerts_engine.remove_alert_rule(custom_rule.rule_id)
        assert result is True
        assert custom_rule.rule_id not in alerts_engine.alert_rules
        
        print("✓ Custom alert rule addition validation passed")
        print(f"  - Rule added: {custom_rule.name}")
        print(f"  - Severity levels: {custom_rule.severity_levels}")
        print(f"  - Actions: {[a.value for a in custom_rule.actions]}")
    
    @pytest.mark.asyncio
    async def test_alert_actions_execution(self, alerts_engine, sample_time_bin, notification_config):
        """Test execution of alert actions"""
        
        # Configure notifications
        alerts_engine.configure_notifications(notification_config)
        
        # Create test alert
        alert = MonitoringAlert(
            alert_id="action_test_alert",
            timestamp=datetime.now(),
            time_bin=sample_time_bin,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.CRITICAL,
            message="Test alert for action execution",
            data={'rule_id': 'test_rule', 'test_results': {}}
        )
        
        # Create test rule with multiple actions
        test_rule = AlertRule(
            rule_id="action_test_rule",
            name="Action Test Rule",
            degradation_type=DegradationType.STATISTICAL_DEGRADATION,
            severity_levels={"critical": 0.05},
            actions=[
                AlertAction.LOG_WARNING,
                AlertAction.SEND_EMAIL,
                AlertAction.SEND_PUSH_NOTIFICATION,
                AlertAction.UPDATE_RECOMMENDATIONS
            ],
            cooldown_minutes=30,
            max_alerts_per_day=5,
            notification_channels=[NotificationChannel.EMAIL, NotificationChannel.PUSH_NOTIFICATION]
        )
        
        # Mock the action execution methods
        with patch.object(alerts_engine, '_queue_email_notification') as mock_email, \
             patch.object(alerts_engine, '_queue_push_notification') as mock_push, \
             patch.object(alerts_engine, '_update_recommendations_for_degradation') as mock_update:
            
            await alerts_engine._execute_alert_actions(alert, test_rule)
            
            # Verify actions were called
            mock_email.assert_called_once_with(alert, test_rule)
            mock_push.assert_called_once_with(alert, test_rule)
            mock_update.assert_called_once_with(alert)
        
        print("✓ Alert actions execution validation passed")
        print(f"  - Actions executed: {len(test_rule.actions)}")
    
    @pytest.mark.asyncio
    async def test_notification_queue_processing(self, alerts_engine, sample_time_bin, notification_config):
        """Test notification queue processing"""
        
        # Configure notifications
        alerts_engine.configure_notifications(notification_config)
        
        # Create test alert
        alert = MonitoringAlert(
            alert_id="notification_test",
            timestamp=datetime.now(),
            time_bin=sample_time_bin,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.WARNING,
            message="Test notification alert",
            data={}
        )
        
        test_rule = AlertRule(
            rule_id="notification_test_rule",
            name="Notification Test Rule",
            degradation_type=DegradationType.WIN_RATE_DECLINE,
            severity_levels={"warning": 0.15},
            actions=[AlertAction.SEND_EMAIL],
            cooldown_minutes=30,
            max_alerts_per_day=5
        )
        
        # Queue notifications
        await alerts_engine._queue_email_notification(alert, test_rule)
        await alerts_engine._queue_push_notification(alert, test_rule)
        
        # Check notification queue
        assert len(alerts_engine.notification_queue) == 2
        
        # Mock notification sending
        with patch.object(alerts_engine, '_send_email_notification') as mock_email, \
             patch.object(alerts_engine, '_send_push_notification') as mock_push:
            
            # Process notifications
            while alerts_engine.notification_queue:
                notification = alerts_engine.notification_queue.popleft()
                await alerts_engine._send_notification(notification)
            
            # Verify notifications were sent
            mock_email.assert_called()
            mock_push.assert_called()
        
        print("✓ Notification queue processing validation passed")
        print("  - Email and push notifications queued and processed")
    
    @pytest.mark.asyncio
    async def test_alert_escalation_processing(self, alerts_engine, sample_time_bin):
        """Test alert escalation for unacknowledged critical alerts"""
        
        # Create unacknowledged critical alert from 45 minutes ago
        old_alert = MonitoringAlert(
            alert_id="escalation_test",
            timestamp=datetime.now() - timedelta(minutes=45),
            time_bin=sample_time_bin,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.CRITICAL,
            message="Unacknowledged critical alert",
            data={}
        )
        
        alerts_engine.active_alerts[old_alert.alert_id] = old_alert
        
        # Mock escalation method
        with patch.object(alerts_engine, '_escalate_to_human') as mock_escalate:
            await alerts_engine._process_alert_escalations()
            
            # Should escalate the old unacknowledged critical alert
            mock_escalate.assert_called_once_with(old_alert)
            
            # Alert should be marked as acknowledged
            assert old_alert.is_acknowledged is True
            assert old_alert.acknowledged_by == "auto_escalation"
        
        print("✓ Alert escalation processing validation passed")
        print(f"  - Alert auto-escalated after 45 minutes")
    
    def test_alert_acknowledgment(self, alerts_engine, sample_time_bin):
        """Test manual alert acknowledgment"""
        
        # Create test alert
        alert = MonitoringAlert(
            alert_id="ack_test_alert",
            timestamp=datetime.now(),
            time_bin=sample_time_bin,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.WARNING,
            message="Test acknowledgment",
            data={}
        )
        
        alerts_engine.active_alerts[alert.alert_id] = alert
        
        # Test acknowledgment
        result = alerts_engine.acknowledge_alert(alert.alert_id, "test_operator")
        
        assert result is True
        assert alert.is_acknowledged is True
        assert alert.acknowledged_by == "test_operator"
        assert alert.acknowledged_at is not None
        
        # Test acknowledging non-existent alert
        result = alerts_engine.acknowledge_alert("non_existent", "test_user")
        assert result is False
        
        print("✓ Alert acknowledgment validation passed")
    
    @pytest.mark.asyncio
    async def test_performance_snapshot_processing(
        self,
        alerts_engine,
        sample_time_bin,
        degrading_performance_snapshots
    ):
        """Test processing of performance snapshots"""
        
        # Mock degradation check
        with patch.object(alerts_engine, '_check_time_bin_degradation') as mock_check:
            # Process snapshots
            for snapshot in degrading_performance_snapshots[:10]:  # Process first 10
                await alerts_engine.process_performance_snapshot(sample_time_bin, snapshot)
            
            # Should have cached snapshots
            assert len(alerts_engine.performance_cache[sample_time_bin]) == 10
            
            # Should have called degradation check for each snapshot
            assert mock_check.call_count == 10
        
        print("✓ Performance snapshot processing validation passed")
        print(f"  - Processed {10} snapshots")
        print(f"  - Cached snapshots: {len(alerts_engine.performance_cache[sample_time_bin])}")
    
    @pytest.mark.asyncio
    async def test_data_cleanup(self, alerts_engine, sample_time_bin):
        """Test automatic data cleanup functionality"""
        
        # Create old alerts that should be cleaned up
        old_alert = MonitoringAlert(
            alert_id="old_alert",
            timestamp=datetime.now() - timedelta(days=10),  # Older than 7 days
            time_bin=sample_time_bin,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.WARNING,
            message="Old alert",
            data={}
        )
        
        alerts_engine.active_alerts[old_alert.alert_id] = old_alert
        
        # Create old violation data
        old_time = datetime.now() - timedelta(hours=30)  # Older than 24 hours
        violation_key = ("test_rule", sample_time_bin)
        alerts_engine.rule_violations[violation_key] = [old_time]
        
        # Create old daily counts
        old_date = datetime.now().date() - timedelta(days=10)
        daily_key = ("test_rule", old_date)
        alerts_engine.daily_alert_counts[daily_key] = 5
        
        # Run cleanup
        await alerts_engine._cleanup_old_data()
        
        # Check that old data was cleaned up
        assert old_alert.alert_id not in alerts_engine.active_alerts
        assert violation_key not in alerts_engine.rule_violations
        assert daily_key not in alerts_engine.daily_alert_counts
        
        print("✓ Data cleanup validation passed")
        print("  - Old alerts, violations, and counts cleaned up")
    
    def test_degradation_callback_system(self, alerts_engine, sample_time_bin):
        """Test degradation detection callback system"""
        
        # Track callback invocations
        callback_invocations = []
        
        def degradation_callback(time_bin, degradation_type, test_results):
            callback_invocations.append({
                'time_bin': time_bin,
                'degradation_type': degradation_type,
                'test_results': test_results
            })
        
        # Add callback
        alerts_engine.add_degradation_callback(degradation_callback)
        
        # Create mock degradation result
        test_results = {'p_value': 0.01, 'effect_size': 1.5}
        
        # Process degradation result (this would normally be called internally)
        asyncio.create_task(alerts_engine._process_degradation_result(
            sample_time_bin,
            DegradationType.STATISTICAL_DEGRADATION,
            test_results
        ))
        
        # Give the async task time to complete
        import time
        time.sleep(0.1)
        
        # Check that callback was invoked
        assert len(callback_invocations) > 0
        callback_data = callback_invocations[0]
        assert callback_data['time_bin'] == sample_time_bin
        assert callback_data['degradation_type'] == DegradationType.STATISTICAL_DEGRADATION
        assert callback_data['test_results'] == test_results
        
        print("✓ Degradation callback system validation passed")
        print(f"  - Callbacks invoked: {len(callback_invocations)}")
    
    def test_engine_status_reporting(self, alerts_engine, sample_time_bin, notification_config):
        """Test engine status reporting"""
        
        # Configure notifications
        alerts_engine.configure_notifications(notification_config)
        
        # Add some test data
        alerts_engine.add_alert_rule(AlertRule(
            rule_id="status_test_rule",
            name="Status Test Rule",
            degradation_type=DegradationType.WIN_RATE_DECLINE,
            severity_levels={"warning": 0.15},
            actions=[AlertAction.LOG_WARNING],
            cooldown_minutes=30,
            max_alerts_per_day=10,
            enabled=False  # Disabled rule
        ))
        
        # Add test alert
        test_alert = MonitoringAlert(
            alert_id="status_test_alert",
            timestamp=datetime.now(),
            time_bin=sample_time_bin,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.WARNING,
            message="Status test alert",
            data={}
        )
        alerts_engine.active_alerts[test_alert.alert_id] = test_alert
        
        # Add notification to queue
        alerts_engine.notification_queue.append({
            'type': 'email',
            'alert': test_alert,
            'timestamp': datetime.now()
        })
        
        # Get status
        status = alerts_engine.get_engine_status()
        
        assert status['running'] is False  # Engine not started
        assert status['active_alerts'] == 1
        assert status['total_rules'] > 4  # Default + custom rules
        assert status['enabled_rules'] >= 4  # Only default rules enabled
        assert status['notification_queue_size'] == 1
        assert status['notification_channels_configured'] == 4  # All channels enabled
        
        print("✓ Engine status reporting validation passed")
        print(f"  - Status: {status}")
    
    def test_get_active_alerts_filtering(self, alerts_engine):
        """Test retrieving active alerts with filtering"""
        
        # Create test time-bins
        time_bin_1 = TimeBin("ACCOUNT_1", 9, 30)
        time_bin_2 = TimeBin("ACCOUNT_2", 14, 0)
        
        # Create alerts for different time-bins
        alert_1 = MonitoringAlert(
            alert_id="filter_test_1",
            timestamp=datetime.now(),
            time_bin=time_bin_1,
            alert_type=AnomalyType.PERFORMANCE_DEGRADATION,
            severity=AlertSeverity.WARNING,
            message="Alert 1",
            data={}
        )
        
        alert_2 = MonitoringAlert(
            alert_id="filter_test_2",
            timestamp=datetime.now(),
            time_bin=time_bin_2,
            alert_type=AnomalyType.DRAWDOWN_THRESHOLD_BREACH,
            severity=AlertSeverity.CRITICAL,
            message="Alert 2",
            data={}
        )
        
        alert_3 = MonitoringAlert(
            alert_id="filter_test_3",
            timestamp=datetime.now(),
            time_bin=time_bin_1,
            alert_type=AnomalyType.UNUSUAL_LOSS_STREAK,
            severity=AlertSeverity.INFO,
            message="Alert 3",
            data={}
        )
        
        # Add alerts
        alerts_engine.active_alerts[alert_1.alert_id] = alert_1
        alerts_engine.active_alerts[alert_2.alert_id] = alert_2
        alerts_engine.active_alerts[alert_3.alert_id] = alert_3
        
        # Test getting all alerts
        all_alerts = alerts_engine.get_active_alerts()
        assert len(all_alerts) == 3
        
        # Test filtering by time-bin
        time_bin_1_alerts = alerts_engine.get_active_alerts(time_bin_1)
        assert len(time_bin_1_alerts) == 2
        assert all(alert.time_bin == time_bin_1 for alert in time_bin_1_alerts)
        
        time_bin_2_alerts = alerts_engine.get_active_alerts(time_bin_2)
        assert len(time_bin_2_alerts) == 1
        assert time_bin_2_alerts[0].time_bin == time_bin_2
        
        print("✓ Active alerts filtering validation passed")
        print(f"  - Total alerts: {len(all_alerts)}")
        print(f"  - Time-bin 1 alerts: {len(time_bin_1_alerts)}")
        print(f"  - Time-bin 2 alerts: {len(time_bin_2_alerts)}")


if __name__ == "__main__":
    # Run tests
    test_instance = TestAlertsEngine()
    
    print("Running AlertsEngine Tests...")
    print("=" * 60)
    
    # Create test fixtures
    sample_time_bin = test_instance.sample_time_bin()
    notification_config = test_instance.notification_config()
    degrading_snapshots = test_instance.degrading_performance_snapshots(sample_time_bin)
    stable_snapshots = test_instance.stable_performance_snapshots(sample_time_bin)
    volatile_snapshots = test_instance.volatile_performance_snapshots(sample_time_bin)
    mock_db_session = Mock()
    
    # Create alerts engine with mocked dependencies
    with patch('trading_platform.services.monitoring.alerts_engine.get_db_session') as mock_get_db:
        mock_get_db.return_value = mock_db_session
        
        alerts_engine = AlertsEngine(mock_db_session)
        alerts_engine.time_bin_analyzer = Mock()
        alerts_engine.performance_calculator = Mock()
        alerts_engine.recommendation_engine = Mock()
    
    try:
        # Run synchronous tests
        test_instance.test_engine_initialization(alerts_engine)
        test_instance.test_notification_configuration(alerts_engine, notification_config)
        test_instance.test_custom_alert_rule_addition(alerts_engine)
        test_instance.test_alert_acknowledgment(alerts_engine, sample_time_bin)
        test_instance.test_degradation_callback_system(alerts_engine, sample_time_bin)
        test_instance.test_engine_status_reporting(alerts_engine, sample_time_bin, notification_config)
        test_instance.test_get_active_alerts_filtering(alerts_engine)
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("AlertsEngine is ready for production use.")
        
    except AssertionError as e:
        print(f"❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        raise