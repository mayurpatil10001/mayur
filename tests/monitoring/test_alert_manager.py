"""
Tests for the alert management system.

Tests alert rule management, threshold checking, and notification delivery.

Requirements: 8.1, 8.3
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from trading_platform.services.monitoring.alert_manager import (
    AlertManager,
    AlertRule,
    Alert,
    NotificationChannel,
    AlertSeverity,
    AlertStatus,
    get_alert_manager
)
from trading_platform.services.monitoring.health_monitor import HealthMonitorService, SystemMetrics, ServiceHealth
from trading_platform.services.monitoring.metrics_collector import MetricsCollector


class TestAlertSeverity:
    """Test AlertSeverity enum."""
    
    def test_values(self):
        """Test alert severity values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.CRITICAL.value == "critical"


class TestAlertStatus:
    """Test AlertStatus enum."""
    
    def test_values(self):
        """Test alert status values."""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.SUPPRESSED.value == "suppressed"


class TestAlertRule:
    """Test AlertRule dataclass."""
    
    def test_creation(self):
        """Test creating alert rule."""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test description",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING
        )
        
        assert rule.rule_id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.metric_name == "cpu_percent"
        assert rule.threshold == 80.0
        assert rule.severity == AlertSeverity.WARNING
        assert rule.duration_minutes == 5  # Default
        assert rule.enabled is True  # Default
        assert rule.tags == {}  # Default
    
    def test_creation_with_tags(self):
        """Test creating alert rule with tags."""
        tags = {"category": "system", "component": "cpu"}
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="Test description",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            tags=tags
        )
        
        assert rule.tags == tags


class TestAlert:
    """Test Alert dataclass."""
    
    def test_creation(self):
        """Test creating alert."""
        triggered_at = datetime.utcnow()
        alert = Alert(
            alert_id="alert_123",
            rule_id="rule_456",
            rule_name="Test Rule",
            message="Test alert message",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            triggered_at=triggered_at
        )
        
        assert alert.alert_id == "alert_123"
        assert alert.rule_id == "rule_456"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.ACTIVE
        assert alert.metric_value == 85.0
        assert alert.triggered_at == triggered_at
        assert alert.resolved_at is None
    
    def test_to_dict(self):
        """Test converting alert to dictionary."""
        triggered_at = datetime(2024, 1, 1, 12, 0, 0)
        resolved_at = datetime(2024, 1, 1, 12, 5, 0)
        
        alert = Alert(
            alert_id="alert_123",
            rule_id="rule_456",
            rule_name="Test Rule",
            message="Test alert message",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.RESOLVED,
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            triggered_at=triggered_at,
            resolved_at=resolved_at
        )
        
        result = alert.to_dict()
        
        assert result['alert_id'] == "alert_123"
        assert result['severity'] == "warning"
        assert result['status'] == "resolved"
        assert result['triggered_at'] == "2024-01-01T12:00:00"
        assert result['resolved_at'] == "2024-01-01T12:05:00"


class TestNotificationChannel:
    """Test NotificationChannel dataclass."""
    
    def test_creation(self):
        """Test creating notification channel."""
        config = {"smtp_server": "localhost"}
        channel = NotificationChannel(
            channel_id="email",
            name="Email Notifications",
            channel_type="email",
            config=config
        )
        
        assert channel.channel_id == "email"
        assert channel.name == "Email Notifications"
        assert channel.channel_type == "email"
        assert channel.config == config
        assert channel.enabled is True  # Default
        assert AlertSeverity.WARNING in channel.severity_filter  # Default


class TestAlertManager:
    """Test AlertManager."""
    
    @pytest.fixture
    def mock_health_monitor(self):
        """Create mock health monitor."""
        monitor = MagicMock(spec=HealthMonitorService)
        
        # Mock current metrics
        metrics = SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_available_gb=8.0,
            disk_usage_percent=70.0,
            disk_free_gb=100.0,
            active_connections=5,
            response_time_avg_ms=150.0,
            error_rate_percent=2.5
        )
        monitor.get_current_metrics.return_value = metrics
        
        # Mock service health
        service_health = {
            "database": ServiceHealth(
                service_name="database",
                status="healthy",
                last_check=datetime.utcnow()
            )
        }
        monitor.get_service_health_status.return_value = service_health
        
        # Mock metrics history
        monitor.get_metrics_history.return_value = [metrics]
        
        return monitor
    
    @pytest.fixture
    def mock_metrics_collector(self):
        """Create mock metrics collector."""
        return MagicMock(spec=MetricsCollector)
    
    @pytest.fixture
    def alert_manager(self, mock_health_monitor, mock_metrics_collector):
        """Create alert manager instance."""
        manager = AlertManager(mock_health_monitor, mock_metrics_collector)
        manager.is_monitoring = False  # Reset monitoring state
        return manager
    
    def test_initialization(self, alert_manager):
        """Test alert manager initialization."""
        assert len(alert_manager.alert_rules) > 0  # Default rules loaded
        assert len(alert_manager.notification_channels) > 0  # Default channels loaded
        assert alert_manager.active_alerts == {}
        assert alert_manager.alert_history == []
        assert not alert_manager.is_monitoring
    
    def test_default_rules_loaded(self, alert_manager):
        """Test that default alert rules are loaded."""
        rule_ids = list(alert_manager.alert_rules.keys())
        
        assert "high_cpu_usage" in rule_ids
        assert "critical_cpu_usage" in rule_ids
        assert "high_memory_usage" in rule_ids
        assert "high_disk_usage" in rule_ids
        assert "high_error_rate" in rule_ids
        assert "slow_response_time" in rule_ids
        assert "service_unhealthy" in rule_ids
    
    def test_default_channels_loaded(self, alert_manager):
        """Test that default notification channels are loaded."""
        channel_ids = list(alert_manager.notification_channels.keys())
        
        assert "log" in channel_ids
        assert "email" in channel_ids
        assert "webhook" in channel_ids
        
        # Log channel should be enabled by default
        assert alert_manager.notification_channels["log"].enabled
        
        # Email and webhook should be disabled by default
        assert not alert_manager.notification_channels["email"].enabled
        assert not alert_manager.notification_channels["webhook"].enabled
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, alert_manager):
        """Test starting and stopping alert monitoring."""
        # Start monitoring
        await alert_manager.start_monitoring()
        assert alert_manager.is_monitoring
        
        # Stop monitoring
        await alert_manager.stop_monitoring()
        assert not alert_manager.is_monitoring
    
    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self, alert_manager):
        """Test starting monitoring when already running."""
        alert_manager.is_monitoring = True
        
        with patch('trading_platform.services.monitoring.alert_manager.logger') as mock_logger:
            await alert_manager.start_monitoring()
            mock_logger.warning.assert_called_once_with("Alert monitoring is already running")
    
    def test_check_condition(self, alert_manager):
        """Test condition checking logic."""
        # Greater than
        assert alert_manager._check_condition("greater_than", 85.0, 80.0)
        assert not alert_manager._check_condition("greater_than", 75.0, 80.0)
        
        # Less than
        assert alert_manager._check_condition("less_than", 75.0, 80.0)
        assert not alert_manager._check_condition("less_than", 85.0, 80.0)
        
        # Equals (with tolerance)
        assert alert_manager._check_condition("equals", 80.0, 80.0)
        assert alert_manager._check_condition("equals", 80.0001, 80.0)
        assert not alert_manager._check_condition("equals", 80.1, 80.0)
        
        # Unknown condition
        with patch('trading_platform.services.monitoring.alert_manager.logger') as mock_logger:
            result = alert_manager._check_condition("unknown", 80.0, 80.0)
            assert not result
            mock_logger.warning.assert_called_once_with("Unknown condition: unknown")
    
    @pytest.mark.asyncio
    async def test_get_metric_value_system_metrics(self, alert_manager, mock_health_monitor):
        """Test getting system metric values."""
        metrics = SystemMetrics(
            timestamp=datetime.utcnow(),
            cpu_percent=85.0,
            memory_percent=75.0,
            memory_available_gb=4.0,
            disk_usage_percent=90.0,
            disk_free_gb=50.0,
            active_connections=10,
            response_time_avg_ms=200.0,
            error_rate_percent=5.0
        )
        
        service_health = {}
        
        # Test various system metrics
        assert await alert_manager._get_metric_value("cpu_percent", metrics, service_health) == 85.0
        assert await alert_manager._get_metric_value("memory_percent", metrics, service_health) == 75.0
        assert await alert_manager._get_metric_value("disk_usage_percent", metrics, service_health) == 90.0
        assert await alert_manager._get_metric_value("error_rate_percent", metrics, service_health) == 5.0
    
    @pytest.mark.asyncio
    async def test_get_metric_value_service_health(self, alert_manager):
        """Test getting service health metric value."""
        metrics = MagicMock()
        
        # Healthy services
        service_health = {
            "database": MagicMock(status="healthy"),
            "api": MagicMock(status="healthy")
        }
        value = await alert_manager._get_metric_value("service_health_status", metrics, service_health)
        assert value == 1.0  # All healthy
        
        # Unhealthy service
        service_health = {
            "database": MagicMock(status="unhealthy"),
            "api": MagicMock(status="healthy")
        }
        value = await alert_manager._get_metric_value("service_health_status", metrics, service_health)
        assert value == 0.0  # Some unhealthy
    
    @pytest.mark.asyncio
    async def test_evaluate_rule_triggered(self, alert_manager):
        """Test rule evaluation when condition is triggered."""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="CPU too high",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_minutes=0  # No duration requirement
        )
        
        # Mock duration check to return True
        alert_manager._check_duration_threshold = AsyncMock(return_value=True)
        alert_manager._send_notifications = AsyncMock()
        
        await alert_manager._evaluate_rule(rule, 85.0)
        
        # Should create active alert
        assert rule.rule_id in alert_manager.active_alerts
        alert = alert_manager.active_alerts[rule.rule_id]
        assert alert.metric_value == 85.0
        assert alert.status == AlertStatus.ACTIVE
        
        # Should add to history
        assert len(alert_manager.alert_history) == 1
        
        # Should send notification
        alert_manager._send_notifications.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_evaluate_rule_resolved(self, alert_manager):
        """Test rule evaluation when condition is resolved."""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="CPU too high",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING
        )
        
        # Create existing active alert
        alert = Alert(
            alert_id="test_alert",
            rule_id=rule.rule_id,
            rule_name=rule.name,
            message="Test message",
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            metric_name=rule.metric_name,
            metric_value=85.0,
            threshold=rule.threshold,
            triggered_at=datetime.utcnow()
        )
        alert_manager.active_alerts[rule.rule_id] = alert
        
        alert_manager._send_notifications = AsyncMock()
        
        # Evaluate with value below threshold
        await alert_manager._evaluate_rule(rule, 75.0)
        
        # Should resolve alert
        assert rule.rule_id not in alert_manager.active_alerts
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None
        
        # Should send resolution notification
        alert_manager._send_notifications.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_duration_threshold(self, alert_manager, mock_health_monitor):
        """Test duration threshold checking."""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="CPU too high",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_minutes=5
        )
        
        # Mock metrics history with consistent high CPU
        base_time = datetime.utcnow()
        metrics_history = []
        for i in range(6):  # 6 minutes of history
            metrics = SystemMetrics(
                timestamp=base_time - timedelta(minutes=i),
                cpu_percent=85.0,  # Consistently above threshold
                memory_percent=60.0,
                memory_available_gb=8.0,
                disk_usage_percent=70.0,
                disk_free_gb=100.0,
                active_connections=5,
                response_time_avg_ms=150.0,
                error_rate_percent=2.5
            )
            metrics_history.append(metrics)
        
        mock_health_monitor.get_metrics_history.return_value = metrics_history
        
        # Should return True since condition persisted for 5+ minutes
        result = await alert_manager._check_duration_threshold(rule, 85.0)
        assert result
    
    @pytest.mark.asyncio
    async def test_check_duration_threshold_not_met(self, alert_manager, mock_health_monitor):
        """Test duration threshold not met."""
        rule = AlertRule(
            rule_id="test_rule",
            name="Test Rule",
            description="CPU too high",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_minutes=5
        )
        
        # Mock metrics history with intermittent high CPU
        base_time = datetime.utcnow()
        metrics_history = []
        for i in range(6):
            cpu_value = 85.0 if i % 2 == 0 else 75.0  # Alternating high/low
            metrics = SystemMetrics(
                timestamp=base_time - timedelta(minutes=i),
                cpu_percent=cpu_value,
                memory_percent=60.0,
                memory_available_gb=8.0,
                disk_usage_percent=70.0,
                disk_free_gb=100.0,
                active_connections=5,
                response_time_avg_ms=150.0,
                error_rate_percent=2.5
            )
            metrics_history.append(metrics)
        
        mock_health_monitor.get_metrics_history.return_value = metrics_history
        
        # Should return False since condition didn't persist
        result = await alert_manager._check_duration_threshold(rule, 85.0)
        assert not result
    
    @pytest.mark.asyncio
    async def test_send_log_notification(self, alert_manager):
        """Test sending log notification."""
        alert = Alert(
            alert_id="test_alert",
            rule_id="test_rule",
            rule_name="Test Rule",
            message="Test alert message",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            triggered_at=datetime.utcnow()
        )
        
        with patch('trading_platform.services.monitoring.alert_manager.logger') as mock_logger:
            await alert_manager._send_log_notification(alert)
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "ALERT TRIGGERED" in call_args
            assert "WARNING" in call_args
    
    def test_add_alert_rule(self, alert_manager):
        """Test adding alert rule."""
        rule = AlertRule(
            rule_id="custom_rule",
            name="Custom Rule",
            description="Custom alert",
            metric_name="memory_percent",
            condition="greater_than",
            threshold=90.0,
            severity=AlertSeverity.CRITICAL
        )
        
        initial_count = len(alert_manager.alert_rules)
        alert_manager.add_alert_rule(rule)
        
        assert len(alert_manager.alert_rules) == initial_count + 1
        assert alert_manager.alert_rules["custom_rule"] == rule
    
    def test_update_alert_rule(self, alert_manager):
        """Test updating alert rule."""
        # Use existing rule
        rule_id = "high_cpu_usage"
        original_rule = alert_manager.alert_rules[rule_id]
        
        # Create updated rule
        updated_rule = AlertRule(
            rule_id=rule_id,
            name="Updated CPU Rule",
            description="Updated description",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=90.0,  # Changed threshold
            severity=AlertSeverity.CRITICAL  # Changed severity
        )
        
        alert_manager.update_alert_rule(updated_rule)
        
        assert alert_manager.alert_rules[rule_id] == updated_rule
        assert alert_manager.alert_rules[rule_id].threshold == 90.0
        assert alert_manager.alert_rules[rule_id].severity == AlertSeverity.CRITICAL
    
    def test_update_nonexistent_rule(self, alert_manager):
        """Test updating nonexistent rule."""
        rule = AlertRule(
            rule_id="nonexistent",
            name="Nonexistent Rule",
            description="Does not exist",
            metric_name="cpu_percent",
            condition="greater_than",
            threshold=80.0,
            severity=AlertSeverity.WARNING
        )
        
        with pytest.raises(ValueError, match="Alert rule nonexistent not found"):
            alert_manager.update_alert_rule(rule)
    
    def test_remove_alert_rule(self, alert_manager):
        """Test removing alert rule."""
        # Use existing rule
        rule_id = "high_cpu_usage"
        initial_count = len(alert_manager.alert_rules)
        
        alert_manager.remove_alert_rule(rule_id)
        
        assert len(alert_manager.alert_rules) == initial_count - 1
        assert rule_id not in alert_manager.alert_rules
    
    def test_remove_nonexistent_rule(self, alert_manager):
        """Test removing nonexistent rule."""
        with pytest.raises(ValueError, match="Alert rule nonexistent not found"):
            alert_manager.remove_alert_rule("nonexistent")
    
    def test_suppress_alert(self, alert_manager):
        """Test suppressing alert."""
        # Create active alert
        rule_id = "test_rule"
        alert = Alert(
            alert_id="test_alert",
            rule_id=rule_id,
            rule_name="Test Rule",
            message="Test message",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.ACTIVE,
            metric_name="cpu_percent",
            metric_value=85.0,
            threshold=80.0,
            triggered_at=datetime.utcnow()
        )
        alert_manager.active_alerts[rule_id] = alert
        
        alert_manager.suppress_alert(rule_id)
        
        assert alert.status == AlertStatus.SUPPRESSED
    
    def test_get_alert_summary(self, alert_manager):
        """Test getting alert summary."""
        # Add some active alerts
        for i, severity in enumerate([AlertSeverity.WARNING, AlertSeverity.CRITICAL]):
            alert = Alert(
                alert_id=f"alert_{i}",
                rule_id=f"rule_{i}",
                rule_name=f"Rule {i}",
                message=f"Message {i}",
                severity=severity,
                status=AlertStatus.ACTIVE,
                metric_name="cpu_percent",
                metric_value=85.0,
                threshold=80.0,
                triggered_at=datetime.utcnow()
            )
            alert_manager.active_alerts[f"rule_{i}"] = alert
        
        summary = alert_manager.get_alert_summary()
        
        assert "timestamp" in summary
        assert "monitoring_status" in summary
        assert "total_rules" in summary
        assert "active_alerts" in summary
        assert "active_by_severity" in summary
        assert summary["active_alerts"] == 2
        assert summary["active_by_severity"]["warning"] == 1
        assert summary["active_by_severity"]["critical"] == 1


class TestGetAlertManager:
    """Test get_alert_manager function."""
    
    def test_singleton_behavior(self):
        """Test that get_alert_manager returns singleton instance."""
        health_monitor = MagicMock()
        metrics_collector = MagicMock()
        
        manager1 = get_alert_manager(health_monitor, metrics_collector)
        manager2 = get_alert_manager(health_monitor, metrics_collector)
        
        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__])