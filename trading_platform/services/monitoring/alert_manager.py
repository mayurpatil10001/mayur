"""
Alert management system for monitoring and notifications.

Provides alert rule management, threshold checking, and notification delivery
for system health and performance monitoring.

Requirements: 8.1, 8.3
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from .health_monitor import HealthMonitorService, SystemMetrics
from .metrics_collector import MetricsCollector


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status states."""
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    """Definition of an alert rule."""
    rule_id: str
    name: str
    description: str
    metric_name: str
    condition: str  # 'greater_than', 'less_than', 'equals'
    threshold: float
    severity: AlertSeverity
    duration_minutes: int = 5  # Alert only if condition persists
    enabled: bool = True
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class Alert:
    """Active or historical alert instance."""
    alert_id: str
    rule_id: str
    rule_name: str
    message: str
    severity: AlertSeverity
    status: AlertStatus
    metric_name: str
    metric_value: float
    threshold: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    tags: Dict[str, str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['triggered_at'] = self.triggered_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        return data


@dataclass
class NotificationChannel:
    """Configuration for notification delivery."""
    channel_id: str
    name: str
    channel_type: str  # 'email', 'webhook', 'log'
    config: Dict[str, Any]
    enabled: bool = True
    severity_filter: List[AlertSeverity] = None
    
    def __post_init__(self):
        if self.severity_filter is None:
            self.severity_filter = [AlertSeverity.WARNING, AlertSeverity.CRITICAL]


class AlertManager:
    """Alert management system for monitoring and notifications."""
    
    def __init__(self, health_monitor: HealthMonitorService, metrics_collector: MetricsCollector):
        self.health_monitor = health_monitor
        self.metrics_collector = metrics_collector
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.notification_channels: Dict[str, NotificationChannel] = {}
        self.is_monitoring = False
        self.check_interval = 60  # Check alerts every minute
        self.max_history_size = 1000
        
        # Setup default alert rules
        self._setup_default_rules()
        
        # Setup default notification channels
        self._setup_default_channels()
    
    def _setup_default_rules(self) -> None:
        """Setup default system monitoring alert rules."""
        default_rules = [
            AlertRule(
                rule_id="high_cpu_usage",
                name="High CPU Usage",
                description="CPU usage is above 80%",
                metric_name="cpu_percent",
                condition="greater_than",
                threshold=80.0,
                severity=AlertSeverity.WARNING,
                duration_minutes=5,
                tags={"category": "system", "component": "cpu"}
            ),
            AlertRule(
                rule_id="critical_cpu_usage",
                name="Critical CPU Usage",
                description="CPU usage is above 95%",
                metric_name="cpu_percent",
                condition="greater_than",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_minutes=2,
                tags={"category": "system", "component": "cpu"}
            ),
            AlertRule(
                rule_id="high_memory_usage",
                name="High Memory Usage",
                description="Memory usage is above 85%",
                metric_name="memory_percent",
                condition="greater_than",
                threshold=85.0,
                severity=AlertSeverity.WARNING,
                duration_minutes=5,
                tags={"category": "system", "component": "memory"}
            ),
            AlertRule(
                rule_id="critical_memory_usage",
                name="Critical Memory Usage",
                description="Memory usage is above 95%",
                metric_name="memory_percent",
                condition="greater_than",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                duration_minutes=2,
                tags={"category": "system", "component": "memory"}
            ),
            AlertRule(
                rule_id="high_disk_usage",
                name="High Disk Usage",
                description="Disk usage is above 90%",
                metric_name="disk_usage_percent",
                condition="greater_than",
                threshold=90.0,
                severity=AlertSeverity.WARNING,
                duration_minutes=10,
                tags={"category": "system", "component": "disk"}
            ),
            AlertRule(
                rule_id="high_error_rate",
                name="High Error Rate",
                description="API error rate is above 10%",
                metric_name="error_rate_percent",
                condition="greater_than",
                threshold=10.0,
                severity=AlertSeverity.WARNING,
                duration_minutes=3,
                tags={"category": "api", "component": "errors"}
            ),
            AlertRule(
                rule_id="slow_response_time",
                name="Slow Response Time",
                description="Average response time is above 1000ms",
                metric_name="response_time_avg_ms",
                condition="greater_than",
                threshold=1000.0,
                severity=AlertSeverity.WARNING,
                duration_minutes=5,
                tags={"category": "api", "component": "performance"}
            ),
            AlertRule(
                rule_id="service_unhealthy",
                name="Service Unhealthy",
                description="A critical service is unhealthy",
                metric_name="service_health_status",
                condition="equals",
                threshold=0.0,  # 0 = unhealthy, 1 = healthy
                severity=AlertSeverity.CRITICAL,
                duration_minutes=1,
                tags={"category": "service", "component": "health"}
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.rule_id] = rule
    
    def _setup_default_channels(self) -> None:
        """Setup default notification channels."""
        # Log notification channel (always enabled)
        self.notification_channels["log"] = NotificationChannel(
            channel_id="log",
            name="System Log",
            channel_type="log",
            config={},
            enabled=True,
            severity_filter=[AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.CRITICAL]
        )
        
        # Email notification channel (disabled by default)
        self.notification_channels["email"] = NotificationChannel(
            channel_id="email",
            name="Email Notifications",
            channel_type="email",
            config={
                "smtp_server": "localhost",
                "smtp_port": 587,
                "from_email": "alerts@tradingplatform.com",
                "to_emails": ["admin@tradingplatform.com"]
            },
            enabled=False,
            severity_filter=[AlertSeverity.WARNING, AlertSeverity.CRITICAL]
        )
        
        # Webhook notification channel (disabled by default)
        self.notification_channels["webhook"] = NotificationChannel(
            channel_id="webhook",
            name="Webhook Notifications",
            channel_type="webhook",
            config={
                "url": "http://localhost:8080/alerts",
                "headers": {"Content-Type": "application/json"},
                "timeout": 10
            },
            enabled=False,
            severity_filter=[AlertSeverity.CRITICAL]
        )
    
    async def start_monitoring(self) -> None:
        """Start alert monitoring."""
        if self.is_monitoring:
            logger.warning("Alert monitoring is already running")
            return
        
        self.is_monitoring = True
        logger.info("Starting alert monitoring")
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop alert monitoring."""
        self.is_monitoring = False
        logger.info("Stopped alert monitoring")
    
    async def _monitoring_loop(self) -> None:
        """Main alert monitoring loop."""
        while self.is_monitoring:
            try:
                await self._check_alerts()
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_alerts(self) -> None:
        """Check all alert rules against current metrics."""
        current_metrics = self.health_monitor.get_current_metrics()
        if not current_metrics:
            return
        
        service_health = self.health_monitor.get_service_health_status()
        
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue
            
            try:
                metric_value = await self._get_metric_value(rule.metric_name, current_metrics, service_health)
                if metric_value is not None:
                    await self._evaluate_rule(rule, metric_value)
                    
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
    
    async def _get_metric_value(self, metric_name: str, metrics: SystemMetrics, service_health: Dict) -> Optional[float]:
        """Get metric value for alert evaluation."""
        if metric_name == "service_health_status":
            # Check if any service is unhealthy
            unhealthy_services = [
                name for name, health in service_health.items()
                if health.status == "unhealthy"
            ]
            return 0.0 if unhealthy_services else 1.0
        
        # Get system metric value
        return getattr(metrics, metric_name, None)
    
    async def _evaluate_rule(self, rule: AlertRule, metric_value: float) -> None:
        """Evaluate an alert rule against a metric value."""
        condition_met = self._check_condition(rule.condition, metric_value, rule.threshold)
        
        if condition_met:
            await self._handle_alert_triggered(rule, metric_value)
        else:
            await self._handle_alert_resolved(rule)
    
    def _check_condition(self, condition: str, value: float, threshold: float) -> bool:
        """Check if alert condition is met."""
        if condition == "greater_than":
            return value > threshold
        elif condition == "less_than":
            return value < threshold
        elif condition == "equals":
            return abs(value - threshold) < 0.001  # Float comparison with tolerance
        else:
            logger.warning(f"Unknown condition: {condition}")
            return False
    
    async def _handle_alert_triggered(self, rule: AlertRule, metric_value: float) -> None:
        """Handle when an alert condition is triggered."""
        # Check if alert is already active
        if rule.rule_id in self.active_alerts:
            return  # Alert already active
        
        # Check if condition has persisted for required duration
        if not await self._check_duration_threshold(rule, metric_value):
            return
        
        # Create new alert
        alert = Alert(
            alert_id=f"{rule.rule_id}_{datetime.utcnow().timestamp()}",
            rule_id=rule.rule_id,
            rule_name=rule.name,
            message=f"{rule.description} (Value: {metric_value:.2f}, Threshold: {rule.threshold:.2f})",
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            metric_name=rule.metric_name,
            metric_value=metric_value,
            threshold=rule.threshold,
            triggered_at=datetime.utcnow(),
            tags=rule.tags.copy()
        )
        
        # Add to active alerts
        self.active_alerts[rule.rule_id] = alert
        
        # Add to history
        self.alert_history.append(alert)
        self._trim_history()
        
        # Send notifications
        await self._send_notifications(alert)
        
        logger.warning(f"Alert triggered: {alert.rule_name} - {alert.message}")
    
    async def _handle_alert_resolved(self, rule: AlertRule) -> None:
        """Handle when an alert condition is resolved."""
        if rule.rule_id not in self.active_alerts:
            return  # No active alert to resolve
        
        alert = self.active_alerts[rule.rule_id]
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        
        # Remove from active alerts
        del self.active_alerts[rule.rule_id]
        
        # Send resolution notification
        await self._send_notifications(alert)
        
        logger.info(f"Alert resolved: {alert.rule_name}")
    
    async def _check_duration_threshold(self, rule: AlertRule, metric_value: float) -> bool:
        """Check if alert condition has persisted for required duration."""
        if rule.duration_minutes <= 0:
            return True  # No duration requirement
        
        # Get recent metrics to check persistence
        cutoff_time = datetime.utcnow() - timedelta(minutes=rule.duration_minutes)
        recent_metrics = self.health_monitor.get_metrics_history(rule.duration_minutes)
        
        if not recent_metrics:
            return False
        
        # Check if condition was met for entire duration
        for metrics in recent_metrics:
            if metrics.timestamp < cutoff_time:
                continue
            
            metric_value_history = getattr(metrics, rule.metric_name, None)
            if metric_value_history is None:
                return False
            
            if not self._check_condition(rule.condition, metric_value_history, rule.threshold):
                return False  # Condition not met during duration
        
        return True
    
    async def _send_notifications(self, alert: Alert) -> None:
        """Send alert notifications through configured channels."""
        for channel in self.notification_channels.values():
            if not channel.enabled:
                continue
            
            if alert.severity not in channel.severity_filter:
                continue
            
            try:
                await self._send_notification(channel, alert)
            except Exception as e:
                logger.error(f"Error sending notification via {channel.name}: {e}")
    
    async def _send_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send notification through specific channel."""
        if channel.channel_type == "log":
            await self._send_log_notification(alert)
        elif channel.channel_type == "email":
            await self._send_email_notification(channel, alert)
        elif channel.channel_type == "webhook":
            await self._send_webhook_notification(channel, alert)
        else:
            logger.warning(f"Unknown notification channel type: {channel.channel_type}")
    
    async def _send_log_notification(self, alert: Alert) -> None:
        """Send notification to system log."""
        status_text = "TRIGGERED" if alert.status == AlertStatus.ACTIVE else "RESOLVED"
        logger.info(f"ALERT {status_text}: [{alert.severity.value.upper()}] {alert.message}")
    
    async def _send_email_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send email notification (placeholder implementation)."""
        # This is a placeholder - in production, implement actual email sending
        logger.info(f"Email notification would be sent for alert: {alert.rule_name}")
    
    async def _send_webhook_notification(self, channel: NotificationChannel, alert: Alert) -> None:
        """Send webhook notification (placeholder implementation)."""
        # This is a placeholder - in production, implement actual webhook posting
        logger.info(f"Webhook notification would be sent for alert: {alert.rule_name}")
    
    def _trim_history(self) -> None:
        """Trim alert history to maintain size limit."""
        if len(self.alert_history) > self.max_history_size:
            self.alert_history = self.alert_history[-self.max_history_size:]
    
    # Public API methods
    
    def add_alert_rule(self, rule: AlertRule) -> None:
        """Add a new alert rule."""
        self.alert_rules[rule.rule_id] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def update_alert_rule(self, rule: AlertRule) -> None:
        """Update an existing alert rule."""
        if rule.rule_id not in self.alert_rules:
            raise ValueError(f"Alert rule {rule.rule_id} not found")
        
        self.alert_rules[rule.rule_id] = rule
        logger.info(f"Updated alert rule: {rule.name}")
    
    def remove_alert_rule(self, rule_id: str) -> None:
        """Remove an alert rule."""
        if rule_id not in self.alert_rules:
            raise ValueError(f"Alert rule {rule_id} not found")
        
        # Remove from active alerts if present
        if rule_id in self.active_alerts:
            del self.active_alerts[rule_id]
        
        del self.alert_rules[rule_id]
        logger.info(f"Removed alert rule: {rule_id}")
    
    def get_alert_rules(self) -> Dict[str, AlertRule]:
        """Get all alert rules."""
        return self.alert_rules.copy()
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all currently active alerts."""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [alert for alert in self.alert_history if alert.triggered_at > cutoff_time]
    
    def suppress_alert(self, rule_id: str) -> None:
        """Suppress an active alert."""
        if rule_id in self.active_alerts:
            self.active_alerts[rule_id].status = AlertStatus.SUPPRESSED
            logger.info(f"Suppressed alert: {rule_id}")
    
    def acknowledge_alert(self, rule_id: str) -> None:
        """Acknowledge an active alert (alias for suppress)."""
        self.suppress_alert(rule_id)
    
    def add_notification_channel(self, channel: NotificationChannel) -> None:
        """Add a notification channel."""
        self.notification_channels[channel.channel_id] = channel
        logger.info(f"Added notification channel: {channel.name}")
    
    def update_notification_channel(self, channel: NotificationChannel) -> None:
        """Update a notification channel."""
        if channel.channel_id not in self.notification_channels:
            raise ValueError(f"Notification channel {channel.channel_id} not found")
        
        self.notification_channels[channel.channel_id] = channel
        logger.info(f"Updated notification channel: {channel.name}")
    
    def get_notification_channels(self) -> Dict[str, NotificationChannel]:
        """Get all notification channels."""
        return self.notification_channels.copy()
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get comprehensive alert summary."""
        active_by_severity = {}
        for severity in AlertSeverity:
            active_by_severity[severity.value] = len([
                alert for alert in self.active_alerts.values()
                if alert.severity == severity and alert.status == AlertStatus.ACTIVE
            ])
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "monitoring_status": "running" if self.is_monitoring else "stopped",
            "total_rules": len(self.alert_rules),
            "enabled_rules": len([r for r in self.alert_rules.values() if r.enabled]),
            "active_alerts": len(self.active_alerts),
            "active_by_severity": active_by_severity,
            "total_channels": len(self.notification_channels),
            "enabled_channels": len([c for c in self.notification_channels.values() if c.enabled]),
            "alerts_last_24h": len(self.get_alert_history(24))
        }


# Global alert manager instance
alert_manager = None


def get_alert_manager(health_monitor: HealthMonitorService, metrics_collector: MetricsCollector) -> AlertManager:
    """Get or create global alert manager instance."""
    global alert_manager
    if alert_manager is None:
        alert_manager = AlertManager(health_monitor, metrics_collector)
    return alert_manager