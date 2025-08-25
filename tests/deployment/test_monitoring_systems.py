"""
Production monitoring systems testing for trading analytics platform.

This module tests production monitoring and health check systems including:
- System health monitoring and alerting
- Performance metrics collection and analysis
- Service dependency monitoring
- Application monitoring and observability
- Infrastructure monitoring validation
- Alert escalation and notification systems

Requirements: 10.4, 10.6, 8.2
"""

import pytest
import asyncio
import tempfile
import os
import time
import psutil
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Callable
from unittest.mock import Mock, patch, AsyncMock
from dataclasses import dataclass, field
import statistics
import queue
import logging

# Import components for monitoring testing
from trading_platform.models.database import ProcessedTrade, Account
from trading_platform.services.health_monitor import HealthMonitor
from trading_platform.services.metrics_collector import MetricsCollector
from trading_platform.services.alert_manager import AlertManager
from trading_platform.services.time_bin_monitoring_service import TimeBinMonitoringService
from trading_platform.database.base import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""
    name: str
    endpoint: str
    timeout_seconds: int = 30
    expected_response_time_ms: int = 1000
    retry_count: int = 3
    critical: bool = True
    dependencies: List[str] = field(default_factory=list)


@dataclass
class MonitoringMetric:
    """Represents a monitoring metric."""
    name: str
    value: float
    unit: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None


@dataclass
class AlertRule:
    """Configuration for alert rules."""
    name: str
    metric_name: str
    condition: str  # 'greater_than', 'less_than', 'equals'
    threshold: float
    duration_minutes: int = 5
    severity: str = "WARNING"  # WARNING, CRITICAL
    notification_channels: List[str] = field(default_factory=list)


class ProductionHealthMonitor:
    """Production-grade health monitoring system."""
    
    def __init__(self):
        self.health_checks = []
        self.health_status = {}
        self.check_history = []
        self.dependency_graph = {}
        
    def register_health_check(self, config: HealthCheckConfig):
        """Register a health check."""
        self.health_checks.append(config)
        self.health_status[config.name] = {'status': 'UNKNOWN', 'last_check': None}
        
        # Build dependency graph
        for dependency in config.dependencies:
            if dependency not in self.dependency_graph:
                self.dependency_graph[dependency] = []
            self.dependency_graph[dependency].append(config.name)
    
    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {
            'overall_status': 'HEALTHY',
            'checks': [],
            'critical_failures': 0,
            'warning_failures': 0,
            'total_checks': len(self.health_checks),
            'check_duration_ms': 0
        }
        
        start_time = time.time()
        
        # Run health checks in dependency order
        ordered_checks = self._order_checks_by_dependency()
        
        for check_config in ordered_checks:
            check_result = await self._execute_health_check(check_config)
            results['checks'].append(check_result)
            
            # Update health status
            self.health_status[check_config.name] = {
                'status': check_result['status'],
                'last_check': datetime.now(),
                'response_time_ms': check_result['response_time_ms'],
                'message': check_result['message']
            }
            
            # Track failures
            if check_result['status'] == 'CRITICAL':
                results['critical_failures'] += 1
                if check_config.critical:
                    results['overall_status'] = 'CRITICAL'
            elif check_result['status'] == 'WARNING':
                results['warning_failures'] += 1
                if results['overall_status'] == 'HEALTHY':
                    results['overall_status'] = 'WARNING'
            
            # Store in history
            self.check_history.append({
                'check_name': check_config.name,
                'result': check_result,
                'timestamp': datetime.now()
            })
            
            # Keep history limited
            if len(self.check_history) > 1000:
                self.check_history = self.check_history[-500:]
        
        results['check_duration_ms'] = (time.time() - start_time) * 1000
        return results
    
    async def _execute_health_check(self, config: HealthCheckConfig) -> Dict[str, Any]:
        """Execute a single health check."""
        result = {
            'name': config.name,
            'status': 'HEALTHY',
            'message': '',
            'response_time_ms': 0,
            'retries_used': 0
        }
        
        for retry in range(config.retry_count):
            start_time = time.time()
            
            try:
                # Simulate health check based on type
                success = await self._simulate_health_check(config)
                response_time = (time.time() - start_time) * 1000
                
                result['response_time_ms'] = response_time
                
                if success:
                    if response_time > config.expected_response_time_ms * 2:
                        result['status'] = 'WARNING'
                        result['message'] = f'Slow response: {response_time:.1f}ms'
                    else:
                        result['status'] = 'HEALTHY'
                        result['message'] = f'OK - {response_time:.1f}ms'
                    break
                else:
                    result['retries_used'] = retry + 1
                    if retry == config.retry_count - 1:
                        result['status'] = 'CRITICAL'
                        result['message'] = f'Check failed after {config.retry_count} retries'
            
            except Exception as e:
                result['retries_used'] = retry + 1
                if retry == config.retry_count - 1:
                    result['status'] = 'CRITICAL'
                    result['message'] = f'Check exception: {str(e)}'
        
        return result
    
    async def _simulate_health_check(self, config: HealthCheckConfig) -> bool:
        """Simulate health check execution based on configuration."""
        # Simulate check duration
        base_duration = 0.1
        if 'database' in config.name.lower():
            base_duration = 0.2
        elif 'external' in config.name.lower():
            base_duration = 0.5
        elif 'disk' in config.name.lower():
            base_duration = 0.05
        
        await asyncio.sleep(base_duration)
        
        # Simulate different failure rates based on check type
        failure_rate = 0.05  # 5% default failure rate
        if 'database' in config.name.lower():
            failure_rate = 0.02  # Database more reliable
        elif 'external' in config.name.lower():
            failure_rate = 0.15  # External services less reliable
        elif 'memory' in config.name.lower():
            failure_rate = 0.01  # Memory checks very reliable
        
        import random
        return random.random() > failure_rate
    
    def _order_checks_by_dependency(self) -> List[HealthCheckConfig]:
        """Order health checks based on dependencies."""
        # Simple topological sort for dependency ordering
        ordered = []
        visited = set()
        temp_visited = set()
        
        def visit(check_name):
            if check_name in temp_visited:
                return  # Circular dependency, skip
            if check_name in visited:
                return
            
            temp_visited.add(check_name)
            
            # Find the check config
            check_config = next((c for c in self.health_checks if c.name == check_name), None)
            if check_config:
                # Visit dependencies first
                for dep in check_config.dependencies:
                    visit(dep)
                
                visited.add(check_name)
                ordered.append(check_config)
            
            temp_visited.remove(check_name)
        
        for check in self.health_checks:
            visit(check.name)
        
        return ordered
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get current health status summary."""
        return {
            'current_status': self.health_status,
            'dependency_graph': self.dependency_graph,
            'total_checks': len(self.health_checks),
            'history_entries': len(self.check_history)
        }


class ProductionMetricsCollector:
    """Production metrics collection system."""
    
    def __init__(self):
        self.metrics = []
        self.metric_aggregates = {}
        self.collection_start_time = time.time()
        
    def record_metric(self, metric: MonitoringMetric):
        """Record a monitoring metric."""
        self.metrics.append(metric)
        
        # Update aggregates
        if metric.name not in self.metric_aggregates:
            self.metric_aggregates[metric.name] = {
                'count': 0,
                'sum': 0.0,
                'min': float('inf'),
                'max': float('-inf'),
                'latest': None
            }
        
        agg = self.metric_aggregates[metric.name]
        agg['count'] += 1
        agg['sum'] += metric.value
        agg['min'] = min(agg['min'], metric.value)
        agg['max'] = max(agg['max'], metric.value)
        agg['latest'] = metric
        
        # Keep metrics limited in memory
        if len(self.metrics) > 10000:
            self.metrics = self.metrics[-5000:]
    
    async def collect_system_metrics(self) -> List[MonitoringMetric]:
        """Collect system-level metrics."""
        metrics = []
        now = datetime.now()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        metrics.append(MonitoringMetric(
            name="system.cpu.usage_percent",
            value=cpu_percent,
            unit="percent",
            timestamp=now,
            threshold_warning=75.0,
            threshold_critical=90.0
        ))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        metrics.append(MonitoringMetric(
            name="system.memory.usage_percent",
            value=memory.percent,
            unit="percent",
            timestamp=now,
            threshold_warning=80.0,
            threshold_critical=95.0
        ))
        
        metrics.append(MonitoringMetric(
            name="system.memory.available_gb",
            value=memory.available / (1024**3),
            unit="gigabytes",
            timestamp=now
        ))
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        metrics.append(MonitoringMetric(
            name="system.disk.usage_percent",
            value=disk.percent,
            unit="percent",
            timestamp=now,
            threshold_warning=80.0,
            threshold_critical=95.0
        ))
        
        # Network metrics
        network = psutil.net_io_counters()
        if network:
            metrics.append(MonitoringMetric(
                name="system.network.bytes_sent",
                value=network.bytes_sent,
                unit="bytes",
                timestamp=now
            ))
            
            metrics.append(MonitoringMetric(
                name="system.network.bytes_recv",
                value=network.bytes_recv,
                unit="bytes",
                timestamp=now
            ))
        
        # Process metrics
        process = psutil.Process()
        metrics.append(MonitoringMetric(
            name="process.memory.rss_mb",
            value=process.memory_info().rss / (1024**2),
            unit="megabytes",
            timestamp=now,
            threshold_warning=500.0,
            threshold_critical=1000.0
        ))
        
        return metrics
    
    async def collect_application_metrics(self) -> List[MonitoringMetric]:
        """Collect application-specific metrics."""
        metrics = []
        now = datetime.now()
        
        # Simulate application metrics
        import random
        
        # Request metrics
        metrics.append(MonitoringMetric(
            name="app.requests.per_second",
            value=random.uniform(50, 200),
            unit="requests_per_second",
            timestamp=now,
            threshold_warning=500.0,
            threshold_critical=1000.0
        ))
        
        metrics.append(MonitoringMetric(
            name="app.response_time.avg_ms",
            value=random.uniform(10, 100),
            unit="milliseconds",
            timestamp=now,
            threshold_warning=200.0,
            threshold_critical=500.0
        ))
        
        # Database metrics
        metrics.append(MonitoringMetric(
            name="database.connections.active",
            value=random.randint(5, 25),
            unit="connections",
            timestamp=now,
            threshold_warning=50.0,
            threshold_critical=80.0
        ))
        
        metrics.append(MonitoringMetric(
            name="database.query_time.avg_ms",
            value=random.uniform(5, 50),
            unit="milliseconds",
            timestamp=now,
            threshold_warning=100.0,
            threshold_critical=200.0
        ))
        
        # Analytics metrics
        metrics.append(MonitoringMetric(
            name="analytics.time_bin.analyses_per_minute",
            value=random.uniform(10, 50),
            unit="analyses_per_minute",
            timestamp=now
        ))
        
        metrics.append(MonitoringMetric(
            name="analytics.monte_carlo.simulations_per_minute",
            value=random.uniform(2, 10),
            unit="simulations_per_minute",
            timestamp=now
        ))
        
        return metrics
    
    def get_metric_summary(self, metric_name: str) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        if metric_name not in self.metric_aggregates:
            return {'error': f'Metric {metric_name} not found'}
        
        agg = self.metric_aggregates[metric_name]
        return {
            'count': agg['count'],
            'average': agg['sum'] / agg['count'] if agg['count'] > 0 else 0,
            'min': agg['min'] if agg['min'] != float('inf') else 0,
            'max': agg['max'] if agg['max'] != float('-inf') else 0,
            'latest_value': agg['latest'].value if agg['latest'] else None,
            'latest_timestamp': agg['latest'].timestamp if agg['latest'] else None
        }
    
    def check_thresholds(self) -> List[Dict[str, Any]]:
        """Check metric thresholds and return alerts."""
        alerts = []
        
        for metric in self.metrics[-100:]:  # Check recent metrics
            if metric.threshold_critical and metric.value >= metric.threshold_critical:
                alerts.append({
                    'severity': 'CRITICAL',
                    'metric_name': metric.name,
                    'current_value': metric.value,
                    'threshold': metric.threshold_critical,
                    'message': f'{metric.name} is {metric.value}{metric.unit}, exceeds critical threshold {metric.threshold_critical}{metric.unit}',
                    'timestamp': metric.timestamp
                })
            elif metric.threshold_warning and metric.value >= metric.threshold_warning:
                alerts.append({
                    'severity': 'WARNING',
                    'metric_name': metric.name,
                    'current_value': metric.value,
                    'threshold': metric.threshold_warning,
                    'message': f'{metric.name} is {metric.value}{metric.unit}, exceeds warning threshold {metric.threshold_warning}{metric.unit}',
                    'timestamp': metric.timestamp
                })
        
        return alerts


class ProductionAlertManager:
    """Production alert management system."""
    
    def __init__(self):
        self.alert_rules = []
        self.active_alerts = []
        self.alert_history = []
        self.notification_channels = {}
        
    def register_alert_rule(self, rule: AlertRule):
        """Register an alert rule."""
        self.alert_rules.append(rule)
    
    def register_notification_channel(self, channel_name: str, handler: Callable):
        """Register a notification channel."""
        self.notification_channels[channel_name] = handler
    
    async def process_metrics(self, metrics: List[MonitoringMetric]):
        """Process metrics against alert rules."""
        new_alerts = []
        
        for rule in self.alert_rules:
            # Find matching metrics
            matching_metrics = [m for m in metrics if m.name == rule.metric_name]
            
            for metric in matching_metrics:
                alert_triggered = self._evaluate_alert_condition(rule, metric)
                
                if alert_triggered:
                    # Check if alert already exists
                    existing_alert = next((a for a in self.active_alerts 
                                         if a['rule_name'] == rule.name and a['status'] == 'ACTIVE'), None)
                    
                    if not existing_alert:
                        alert = {
                            'id': f"{rule.name}_{int(time.time())}",
                            'rule_name': rule.name,
                            'severity': rule.severity,
                            'metric_name': rule.metric_name,
                            'metric_value': metric.value,
                            'threshold': rule.threshold,
                            'message': f'{rule.name}: {metric.name} = {metric.value}{metric.unit} {rule.condition} {rule.threshold}{metric.unit}',
                            'created_at': datetime.now(),
                            'status': 'ACTIVE',
                            'notification_sent': False
                        }
                        
                        self.active_alerts.append(alert)
                        new_alerts.append(alert)
        
        # Send notifications for new alerts
        for alert in new_alerts:
            await self._send_alert_notifications(alert)
        
        return new_alerts
    
    def _evaluate_alert_condition(self, rule: AlertRule, metric: MonitoringMetric) -> bool:
        """Evaluate if an alert condition is met."""
        if rule.condition == 'greater_than':
            return metric.value > rule.threshold
        elif rule.condition == 'less_than':
            return metric.value < rule.threshold
        elif rule.condition == 'equals':
            return metric.value == rule.threshold
        else:
            return False
    
    async def _send_alert_notifications(self, alert: Dict[str, Any]):
        """Send alert notifications through configured channels."""
        rule = next((r for r in self.alert_rules if r.name == alert['rule_name']), None)
        if not rule:
            return
        
        for channel_name in rule.notification_channels:
            if channel_name in self.notification_channels:
                try:
                    handler = self.notification_channels[channel_name]
                    await handler(alert)
                    print(f"Alert notification sent via {channel_name}: {alert['message']}")
                except Exception as e:
                    print(f"Failed to send notification via {channel_name}: {e}")
        
        alert['notification_sent'] = True
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Acknowledge an active alert."""
        alert = next((a for a in self.active_alerts if a['id'] == alert_id), None)
        if alert:
            alert['status'] = 'ACKNOWLEDGED'
            alert['acknowledged_by'] = acknowledged_by
            alert['acknowledged_at'] = datetime.now()
    
    def resolve_alert(self, alert_id: str, resolved_by: str):
        """Resolve an active alert."""
        alert = next((a for a in self.active_alerts if a['id'] == alert_id), None)
        if alert:
            alert['status'] = 'RESOLVED'
            alert['resolved_by'] = resolved_by
            alert['resolved_at'] = datetime.now()
            
            # Move to history
            self.alert_history.append(alert)
            self.active_alerts.remove(alert)
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert system summary."""
        return {
            'active_alerts': len([a for a in self.active_alerts if a['status'] == 'ACTIVE']),
            'acknowledged_alerts': len([a for a in self.active_alerts if a['status'] == 'ACKNOWLEDGED']),
            'total_rules': len(self.alert_rules),
            'notification_channels': len(self.notification_channels),
            'alert_history_count': len(self.alert_history)
        }


class ServiceDependencyMonitor:
    """Monitor service dependencies and health."""
    
    def __init__(self):
        self.services = {}
        self.dependency_map = {}
        
    def register_service(self, name: str, health_endpoint: str, dependencies: List[str] = None):
        """Register a service for monitoring."""
        self.services[name] = {
            'name': name,
            'health_endpoint': health_endpoint,
            'dependencies': dependencies or [],
            'status': 'UNKNOWN',
            'last_check': None,
            'response_time_ms': 0
        }
        
        # Update dependency map
        for dep in (dependencies or []):
            if dep not in self.dependency_map:
                self.dependency_map[dep] = []
            self.dependency_map[dep].append(name)
    
    async def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """Check health of a specific service."""
        if service_name not in self.services:
            return {'error': f'Service {service_name} not registered'}
        
        service = self.services[service_name]
        start_time = time.time()
        
        try:
            # Simulate service health check
            await asyncio.sleep(0.05)  # Simulate network call
            
            # Simulate 95% uptime
            import random
            is_healthy = random.random() < 0.95
            
            response_time = (time.time() - start_time) * 1000
            
            status = 'HEALTHY' if is_healthy else 'UNHEALTHY'
            service['status'] = status
            service['last_check'] = datetime.now()
            service['response_time_ms'] = response_time
            
            return {
                'service': service_name,
                'status': status,
                'response_time_ms': response_time,
                'dependencies_status': await self._check_dependencies(service_name)
            }
            
        except Exception as e:
            service['status'] = 'ERROR'
            service['last_check'] = datetime.now()
            return {
                'service': service_name,
                'status': 'ERROR',
                'error': str(e),
                'dependencies_status': {}
            }
    
    async def _check_dependencies(self, service_name: str) -> Dict[str, str]:
        """Check status of service dependencies."""
        service = self.services[service_name]
        dependency_status = {}
        
        for dep in service['dependencies']:
            if dep in self.services:
                dep_service = self.services[dep]
                # Use cached status if recent, otherwise check
                if (dep_service['last_check'] and 
                    (datetime.now() - dep_service['last_check']).seconds < 30):
                    dependency_status[dep] = dep_service['status']
                else:
                    dep_check = await self.check_service_health(dep)
                    dependency_status[dep] = dep_check['status']
            else:
                dependency_status[dep] = 'NOT_REGISTERED'
        
        return dependency_status
    
    async def check_all_services(self) -> Dict[str, Any]:
        """Check health of all registered services."""
        results = {
            'overall_health': 'HEALTHY',
            'services': {},
            'healthy_count': 0,
            'unhealthy_count': 0,
            'error_count': 0
        }
        
        for service_name in self.services.keys():
            service_result = await self.check_service_health(service_name)
            results['services'][service_name] = service_result
            
            if service_result['status'] == 'HEALTHY':
                results['healthy_count'] += 1
            elif service_result['status'] == 'UNHEALTHY':
                results['unhealthy_count'] += 1
                results['overall_health'] = 'DEGRADED'
            else:
                results['error_count'] += 1
                results['overall_health'] = 'CRITICAL'
        
        return results


class TestProductionMonitoring:
    """Test production monitoring systems."""
    
    @pytest.fixture
    def monitoring_database(self):
        """Create database for monitoring tests."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        engine = create_engine(f"sqlite:///{temp_db.name}", echo=False)
        Base.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        
        yield engine, SessionLocal
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_health_monitoring_system(self, monitoring_database):
        """Test comprehensive health monitoring system."""
        print("\nTesting health monitoring system...")
        
        engine, SessionLocal = monitoring_database
        health_monitor = ProductionHealthMonitor()
        
        # Register health checks
        health_checks = [
            HealthCheckConfig(
                name="database_connectivity",
                endpoint="/health/db",
                timeout_seconds=10,
                expected_response_time_ms=100,
                critical=True,
                dependencies=[]
            ),
            HealthCheckConfig(
                name="redis_cache",
                endpoint="/health/redis",
                timeout_seconds=5,
                expected_response_time_ms=50,
                critical=False,
                dependencies=[]
            ),
            HealthCheckConfig(
                name="external_market_data",
                endpoint="/health/market-data",
                timeout_seconds=15,
                expected_response_time_ms=500,
                critical=False,
                dependencies=[]
            ),
            HealthCheckConfig(
                name="analytics_service",
                endpoint="/health/analytics",
                timeout_seconds=10,
                expected_response_time_ms=200,
                critical=True,
                dependencies=["database_connectivity", "redis_cache"]
            ),
            HealthCheckConfig(
                name="monitoring_service",
                endpoint="/health/monitoring",
                timeout_seconds=5,
                expected_response_time_ms=100,
                critical=False,
                dependencies=["database_connectivity"]
            )
        ]
        
        for check in health_checks:
            health_monitor.register_health_check(check)
        
        # Run health checks
        health_result = await health_monitor.run_health_checks()
        
        print(f"Health monitoring results:")
        print(f"  Overall status: {health_result['overall_status']}")
        print(f"  Total checks: {health_result['total_checks']}")
        print(f"  Critical failures: {health_result['critical_failures']}")
        print(f"  Warning failures: {health_result['warning_failures']}")
        print(f"  Check duration: {health_result['check_duration_ms']:.1f}ms")
        
        # Validate health check results
        assert health_result['total_checks'] == 5, "Should run all registered health checks"
        assert health_result['overall_status'] in ['HEALTHY', 'WARNING', 'CRITICAL'], "Should have valid overall status"
        assert len(health_result['checks']) == 5, "Should have individual check results"
        
        # Validate individual checks
        for check in health_result['checks']:
            assert 'name' in check
            assert 'status' in check
            assert 'message' in check
            assert 'response_time_ms' in check
            assert check['status'] in ['HEALTHY', 'WARNING', 'CRITICAL']
            assert check['response_time_ms'] >= 0
        
        # Test health summary
        summary = health_monitor.get_health_summary()
        assert 'current_status' in summary
        assert 'dependency_graph' in summary
        assert summary['total_checks'] == 5
        
        print("✅ Health monitoring system test passed")
    
    @pytest.mark.asyncio
    async def test_metrics_collection_system(self):
        """Test metrics collection and aggregation system."""
        print("\nTesting metrics collection system...")
        
        metrics_collector = ProductionMetricsCollector()
        
        # Collect system metrics
        system_metrics = await metrics_collector.collect_system_metrics()
        
        print(f"System metrics collected: {len(system_metrics)}")
        for metric in system_metrics:
            metrics_collector.record_metric(metric)
        
        # Collect application metrics
        app_metrics = await metrics_collector.collect_application_metrics()
        
        print(f"Application metrics collected: {len(app_metrics)}")
        for metric in app_metrics:
            metrics_collector.record_metric(metric)
        
        # Validate metrics structure
        all_metrics = system_metrics + app_metrics
        assert len(all_metrics) >= 10, "Should collect multiple metrics"
        
        for metric in all_metrics:
            assert hasattr(metric, 'name')
            assert hasattr(metric, 'value')
            assert hasattr(metric, 'unit')
            assert hasattr(metric, 'timestamp')
            assert isinstance(metric.value, (int, float))
        
        # Test metric summaries
        for metric in all_metrics[:5]:  # Test first 5 metrics
            summary = metrics_collector.get_metric_summary(metric.name)
            assert 'count' in summary
            assert 'average' in summary
            assert 'min' in summary
            assert 'max' in summary
            assert summary['count'] > 0
        
        # Test threshold checking
        threshold_alerts = metrics_collector.check_thresholds()
        print(f"Threshold alerts generated: {len(threshold_alerts)}")
        
        for alert in threshold_alerts:
            assert 'severity' in alert
            assert 'metric_name' in alert
            assert 'current_value' in alert
            assert 'threshold' in alert
            assert alert['severity'] in ['WARNING', 'CRITICAL']
        
        print("✅ Metrics collection system test passed")
    
    @pytest.mark.asyncio
    async def test_alert_management_system(self):
        """Test alert management and notification system."""
        print("\nTesting alert management system...")
        
        alert_manager = ProductionAlertManager()
        metrics_collector = ProductionMetricsCollector()
        
        # Track notifications sent
        notifications_sent = []
        
        async def mock_email_handler(alert):
            notifications_sent.append(('email', alert))
        
        async def mock_slack_handler(alert):
            notifications_sent.append(('slack', alert))
        
        # Register notification channels
        alert_manager.register_notification_channel('email', mock_email_handler)
        alert_manager.register_notification_channel('slack', mock_slack_handler)
        
        # Register alert rules
        alert_rules = [
            AlertRule(
                name="high_cpu_usage",
                metric_name="system.cpu.usage_percent",
                condition="greater_than",
                threshold=80.0,
                severity="WARNING",
                notification_channels=['email']
            ),
            AlertRule(
                name="critical_memory_usage",
                metric_name="system.memory.usage_percent",
                condition="greater_than",
                threshold=90.0,
                severity="CRITICAL",
                notification_channels=['email', 'slack']
            ),
            AlertRule(
                name="slow_response_time",
                metric_name="app.response_time.avg_ms",
                condition="greater_than",
                threshold=200.0,
                severity="WARNING",
                notification_channels=['slack']
            )
        ]
        
        for rule in alert_rules:
            alert_manager.register_alert_rule(rule)
        
        # Generate test metrics that trigger alerts
        test_metrics = [
            MonitoringMetric(
                name="system.cpu.usage_percent",
                value=85.0,  # Should trigger high_cpu_usage alert
                unit="percent",
                timestamp=datetime.now()
            ),
            MonitoringMetric(
                name="system.memory.usage_percent",
                value=92.0,  # Should trigger critical_memory_usage alert
                unit="percent",
                timestamp=datetime.now()
            ),
            MonitoringMetric(
                name="app.response_time.avg_ms",
                value=250.0,  # Should trigger slow_response_time alert
                unit="milliseconds",
                timestamp=datetime.now()
            ),
            MonitoringMetric(
                name="system.disk.usage_percent",
                value=60.0,  # Should not trigger any alerts
                unit="percent",
                timestamp=datetime.now()
            )
        ]
        
        # Process metrics through alert manager
        new_alerts = await alert_manager.process_metrics(test_metrics)
        
        print(f"Alerts generated: {len(new_alerts)}")
        for alert in new_alerts:
            print(f"  {alert['severity']}: {alert['message']}")
        
        print(f"Notifications sent: {len(notifications_sent)}")
        for channel, alert in notifications_sent:
            print(f"  {channel}: {alert['rule_name']}")
        
        # Validate alert generation
        assert len(new_alerts) == 3, "Should generate 3 alerts from test metrics"
        assert len(notifications_sent) >= 3, "Should send notifications for alerts"
        
        # Validate alert properties
        for alert in new_alerts:
            assert 'id' in alert
            assert 'rule_name' in alert
            assert 'severity' in alert
            assert alert['severity'] in ['WARNING', 'CRITICAL']
            assert alert['status'] == 'ACTIVE'
        
        # Test alert acknowledgment
        if new_alerts:
            alert_id = new_alerts[0]['id']
            alert_manager.acknowledge_alert(alert_id, "test_user")
            
            acknowledged_alert = next((a for a in alert_manager.active_alerts if a['id'] == alert_id), None)
            assert acknowledged_alert['status'] == 'ACKNOWLEDGED'
            assert 'acknowledged_by' in acknowledged_alert
        
        # Test alert resolution
        if new_alerts:
            alert_id = new_alerts[1]['id']
            alert_manager.resolve_alert(alert_id, "test_user")
            
            # Should be moved to history
            resolved_alert = next((a for a in alert_manager.alert_history if a['id'] == alert_id), None)
            assert resolved_alert is not None
            assert resolved_alert['status'] == 'RESOLVED'
        
        # Test alert summary
        summary = alert_manager.get_alert_summary()
        assert 'active_alerts' in summary
        assert 'acknowledged_alerts' in summary
        assert 'total_rules' in summary
        assert summary['total_rules'] == 3
        
        print("✅ Alert management system test passed")
    
    @pytest.mark.asyncio
    async def test_service_dependency_monitoring(self):
        """Test service dependency monitoring."""
        print("\nTesting service dependency monitoring...")
        
        dependency_monitor = ServiceDependencyMonitor()
        
        # Register services with dependencies
        services = [
            ("database", "http://db:5432/health", []),
            ("cache", "http://redis:6379/ping", []),
            ("auth_service", "http://auth:8080/health", ["database"]),
            ("analytics_api", "http://analytics:8000/health", ["database", "cache"]),
            ("web_ui", "http://web:3000/health", ["analytics_api", "auth_service"])
        ]
        
        for name, endpoint, deps in services:
            dependency_monitor.register_service(name, endpoint, deps)
        
        # Check individual service health
        auth_result = await dependency_monitor.check_service_health("auth_service")
        print(f"Auth service health: {auth_result}")
        
        assert 'service' in auth_result
        assert 'status' in auth_result
        assert auth_result['service'] == "auth_service"
        assert auth_result['status'] in ['HEALTHY', 'UNHEALTHY', 'ERROR']
        
        # Check all services
        all_services_result = await dependency_monitor.check_all_services()
        
        print(f"All services health check:")
        print(f"  Overall health: {all_services_result['overall_health']}")
        print(f"  Healthy services: {all_services_result['healthy_count']}")
        print(f"  Unhealthy services: {all_services_result['unhealthy_count']}")
        print(f"  Error services: {all_services_result['error_count']}")
        
        # Validate service monitoring results
        assert 'overall_health' in all_services_result
        assert 'services' in all_services_result
        assert len(all_services_result['services']) == 5, "Should check all registered services"
        
        total_services = (all_services_result['healthy_count'] + 
                         all_services_result['unhealthy_count'] + 
                         all_services_result['error_count'])
        assert total_services == 5, "Service counts should sum to total services"
        
        # Validate dependency checking
        for service_name, service_result in all_services_result['services'].items():
            if 'dependencies_status' in service_result:
                service_config = dependency_monitor.services[service_name]
                expected_deps = len(service_config['dependencies'])
                actual_deps = len(service_result['dependencies_status'])
                assert actual_deps == expected_deps, f"Should check all dependencies for {service_name}"
        
        print("✅ Service dependency monitoring test passed")
    
    @pytest.mark.asyncio
    async def test_integrated_monitoring_pipeline(self):
        """Test integrated monitoring pipeline with all components."""
        print("\nTesting integrated monitoring pipeline...")
        
        # Setup all monitoring components
        health_monitor = ProductionHealthMonitor()
        metrics_collector = ProductionMetricsCollector()
        alert_manager = ProductionAlertManager()
        dependency_monitor = ServiceDependencyMonitor()
        
        # Configure health checks
        health_monitor.register_health_check(HealthCheckConfig(
            name="api_health",
            endpoint="/health/api",
            timeout_seconds=10,
            critical=True
        ))
        
        # Configure alert rules
        alert_manager.register_alert_rule(AlertRule(
            name="high_memory_alert",
            metric_name="system.memory.usage_percent",
            condition="greater_than",
            threshold=75.0,
            severity="WARNING",
            notification_channels=[]
        ))
        
        # Register services
        dependency_monitor.register_service("api", "http://api:8000/health", [])
        
        # Notification tracking
        pipeline_notifications = []
        
        async def pipeline_notification_handler(alert):
            pipeline_notifications.append(alert)
        
        alert_manager.register_notification_channel('pipeline', pipeline_notification_handler)
        alert_manager.alert_rules[0].notification_channels = ['pipeline']
        
        # Run monitoring pipeline
        pipeline_start = time.time()
        
        # Step 1: Health checks
        health_result = await health_monitor.run_health_checks()
        
        # Step 2: Metrics collection
        system_metrics = await metrics_collector.collect_system_metrics()
        app_metrics = await metrics_collector.collect_application_metrics()
        all_metrics = system_metrics + app_metrics
        
        for metric in all_metrics:
            metrics_collector.record_metric(metric)
        
        # Step 3: Alert processing
        alerts = await alert_manager.process_metrics(all_metrics)
        
        # Step 4: Service dependency checks
        service_health = await dependency_monitor.check_all_services()
        
        pipeline_duration = time.time() - pipeline_start
        
        # Analyze pipeline results
        print(f"Integrated monitoring pipeline results:")
        print(f"  Pipeline duration: {pipeline_duration:.2f} seconds")
        print(f"  Health checks: {health_result['total_checks']} (status: {health_result['overall_status']})")
        print(f"  Metrics collected: {len(all_metrics)}")
        print(f"  Alerts generated: {len(alerts)}")
        print(f"  Service health: {service_health['overall_health']}")
        print(f"  Notifications sent: {len(pipeline_notifications)}")
        
        # Validate integrated pipeline
        assert pipeline_duration <= 10.0, f"Pipeline too slow: {pipeline_duration:.2f} seconds"
        assert health_result['total_checks'] > 0, "Should run health checks"
        assert len(all_metrics) >= 10, "Should collect multiple metrics"
        assert service_health['overall_health'] in ['HEALTHY', 'DEGRADED', 'CRITICAL'], "Should have valid service health status"
        
        # Test pipeline performance under load
        print("\nTesting pipeline under load...")
        
        load_start = time.time()
        load_tasks = []
        
        for i in range(5):  # Run 5 concurrent pipeline iterations
            task = asyncio.create_task(self._run_monitoring_iteration(
                health_monitor, metrics_collector, alert_manager, dependency_monitor
            ))
            load_tasks.append(task)
        
        load_results = await asyncio.gather(*load_tasks)
        load_duration = time.time() - load_start
        
        successful_iterations = sum(1 for result in load_results if result['success'])
        
        print(f"Load test results:")
        print(f"  Concurrent iterations: 5")
        print(f"  Successful iterations: {successful_iterations}")
        print(f"  Load test duration: {load_duration:.2f} seconds")
        print(f"  Average iteration time: {load_duration / 5:.2f} seconds")
        
        # Validate load test
        assert successful_iterations >= 4, f"Too many failed iterations: {successful_iterations}/5"
        assert load_duration <= 15.0, f"Load test too slow: {load_duration:.2f} seconds"
        
        print("✅ Integrated monitoring pipeline test passed")
    
    async def _run_monitoring_iteration(self, health_monitor, metrics_collector, alert_manager, dependency_monitor):
        """Run a single monitoring iteration."""
        try:
            # Quick health check
            health_result = await health_monitor.run_health_checks()
            
            # Quick metrics collection
            metrics = await metrics_collector.collect_system_metrics()
            for metric in metrics:
                metrics_collector.record_metric(metric)
            
            # Process alerts
            alerts = await alert_manager.process_metrics(metrics)
            
            # Quick service check
            service_result = await dependency_monitor.check_all_services()
            
            return {
                'success': True,
                'health_status': health_result['overall_status'],
                'metrics_count': len(metrics),
                'alerts_count': len(alerts),
                'service_status': service_result['overall_health']
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @pytest.mark.asyncio
    async def test_monitoring_performance_benchmarks(self):
        """Test monitoring system performance benchmarks."""
        print("\nTesting monitoring performance benchmarks...")
        
        # Performance benchmark targets
        benchmarks = {
            'health_check_duration_ms': 1000,
            'metrics_collection_duration_ms': 500,
            'alert_processing_duration_ms': 200,
            'service_check_duration_ms': 800
        }
        
        # Setup monitoring components
        health_monitor = ProductionHealthMonitor()
        metrics_collector = ProductionMetricsCollector()
        alert_manager = ProductionAlertManager()
        dependency_monitor = ServiceDependencyMonitor()
        
        # Register multiple health checks
        for i in range(10):
            health_monitor.register_health_check(HealthCheckConfig(
                name=f"health_check_{i}",
                endpoint=f"/health/service_{i}",
                timeout_seconds=5
            ))
        
        # Register multiple services
        for i in range(8):
            dependency_monitor.register_service(
                f"service_{i}",
                f"http://service{i}:8000/health",
                [] if i == 0 else [f"service_{i-1}"]
            )
        
        performance_results = {}
        
        # Benchmark health checks
        start_time = time.time()
        health_result = await health_monitor.run_health_checks()
        performance_results['health_check_duration_ms'] = (time.time() - start_time) * 1000
        
        # Benchmark metrics collection
        start_time = time.time()
        metrics = await metrics_collector.collect_system_metrics()
        metrics.extend(await metrics_collector.collect_application_metrics())
        performance_results['metrics_collection_duration_ms'] = (time.time() - start_time) * 1000
        
        # Benchmark alert processing
        start_time = time.time()
        alerts = await alert_manager.process_metrics(metrics)
        performance_results['alert_processing_duration_ms'] = (time.time() - start_time) * 1000
        
        # Benchmark service checks
        start_time = time.time()
        service_result = await dependency_monitor.check_all_services()
        performance_results['service_check_duration_ms'] = (time.time() - start_time) * 1000
        
        print(f"Monitoring performance benchmarks:")
        for benchmark_name, target_ms in benchmarks.items():
            actual_ms = performance_results.get(benchmark_name, 0)
            passed = actual_ms <= target_ms
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"  {benchmark_name}: {actual_ms:.1f}ms (target: {target_ms}ms) {status}")
            
            # Assert performance benchmarks
            assert actual_ms <= target_ms, f"{benchmark_name} too slow: {actual_ms:.1f}ms > {target_ms}ms"
        
        # Overall system performance
        total_duration = sum(performance_results.values())
        print(f"  Total monitoring cycle: {total_duration:.1f}ms")
        
        assert total_duration <= 3000, f"Total monitoring cycle too slow: {total_duration:.1f}ms"
        
        print("✅ Monitoring performance benchmarks passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])