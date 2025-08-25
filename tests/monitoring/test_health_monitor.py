"""
Tests for the health monitoring service.

Tests system health monitoring functionality including metrics collection,
service health checks, and status reporting.

Requirements: 8.1, 8.3
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

from trading_platform.services.monitoring.health_monitor import (
    HealthMonitorService,
    SystemMetrics,
    ServiceHealth
)


class TestSystemMetrics:
    """Test SystemMetrics dataclass."""
    
    def test_to_dict(self):
        """Test converting SystemMetrics to dictionary."""
        metrics = SystemMetrics(
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            cpu_percent=50.0,
            memory_percent=60.0,
            memory_available_gb=8.5,
            disk_usage_percent=70.0,
            disk_free_gb=100.0,
            active_connections=5,
            response_time_avg_ms=150.0,
            error_rate_percent=2.5
        )
        
        result = metrics.to_dict()
        
        assert result['timestamp'] == '2024-01-01T12:00:00'
        assert result['cpu_percent'] == 50.0
        assert result['memory_percent'] == 60.0
        assert result['memory_available_gb'] == 8.5
        assert result['disk_usage_percent'] == 70.0
        assert result['disk_free_gb'] == 100.0
        assert result['active_connections'] == 5
        assert result['response_time_avg_ms'] == 150.0
        assert result['error_rate_percent'] == 2.5


class TestServiceHealth:
    """Test ServiceHealth dataclass."""
    
    def test_to_dict(self):
        """Test converting ServiceHealth to dictionary."""
        health = ServiceHealth(
            service_name="database",
            status="healthy",
            last_check=datetime(2024, 1, 1, 12, 0, 0),
            response_time_ms=50.0,
            uptime_percent=99.9
        )
        
        result = health.to_dict()
        
        assert result['service_name'] == "database"
        assert result['status'] == "healthy"
        assert result['last_check'] == '2024-01-01T12:00:00'
        assert result['response_time_ms'] == 50.0
        assert result['uptime_percent'] == 99.9


class TestHealthMonitorService:
    """Test HealthMonitorService."""
    
    @pytest.fixture
    def health_monitor(self):
        """Create health monitor instance for testing."""
        return HealthMonitorService()
        
    def test_initialization(self, health_monitor):
        """Test health monitor initialization."""
        assert health_monitor.metrics_history == []
        assert health_monitor.service_health == {}
        assert health_monitor.max_history_size == 1000
        assert health_monitor.check_interval == 30
        assert not health_monitor.is_monitoring
        
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, health_monitor):
        """Test starting and stopping monitoring."""
        # Start monitoring
        await health_monitor.start_monitoring()
        assert health_monitor.is_monitoring
        
        # Stop monitoring
        await health_monitor.stop_monitoring()
        assert not health_monitor.is_monitoring
        
    @pytest.mark.asyncio
    async def test_start_monitoring_already_running(self, health_monitor):
        """Test starting monitoring when already running."""
        health_monitor.is_monitoring = True
        
        with patch('trading_platform.services.monitoring.health_monitor.logger') as mock_logger:
            await health_monitor.start_monitoring()
            mock_logger.warning.assert_called_once_with("Monitoring is already running")
            
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    @pytest.mark.asyncio
    async def test_collect_system_metrics(self, mock_disk, mock_memory, mock_cpu, health_monitor):
        """Test collecting system metrics."""
        # Mock psutil functions
        mock_cpu.return_value = 50.0
        mock_memory.return_value = MagicMock(percent=60.0, available=8.5 * 1024**3)
        mock_disk.return_value = MagicMock(
            total=100 * 1024**3,
            used=70 * 1024**3,
            free=30 * 1024**3
        )
        
        # Mock other methods
        health_monitor._get_active_connections = AsyncMock(return_value=5)
        health_monitor._calculate_performance_metrics = MagicMock(return_value=(150.0, 2.5))
        
        metrics = await health_monitor._collect_system_metrics()
        
        assert isinstance(metrics, SystemMetrics)
        assert metrics.cpu_percent == 50.0
        assert metrics.memory_percent == 60.0
        assert metrics.memory_available_gb == 8.5
        assert metrics.disk_usage_percent == 70.0
        assert metrics.disk_free_gb == 30.0
        assert metrics.active_connections == 5
        assert metrics.response_time_avg_ms == 150.0
        assert metrics.error_rate_percent == 2.5
        
    @pytest.mark.asyncio
    async def test_collect_system_metrics_error(self, health_monitor):
        """Test collecting system metrics with error."""
        with patch('psutil.cpu_percent', side_effect=Exception("Test error")):
            metrics = await health_monitor._collect_system_metrics()
            
            # Should return default metrics on error
            assert isinstance(metrics, SystemMetrics)
            assert metrics.cpu_percent == 0.0
            assert metrics.memory_percent == 0.0
            assert metrics.error_rate_percent == 100.0
            
    def test_add_metrics(self, health_monitor):
        """Test adding metrics to history."""
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
        
        health_monitor._add_metrics(metrics)
        
        assert len(health_monitor.metrics_history) == 1
        assert health_monitor.metrics_history[0] == metrics
        
    def test_add_metrics_trim_history(self, health_monitor):
        """Test trimming metrics history when it exceeds limit."""
        health_monitor.max_history_size = 3
        
        # Add 5 metrics
        for i in range(5):
            metrics = SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=float(i),
                memory_percent=60.0,
                memory_available_gb=8.0,
                disk_usage_percent=70.0,
                disk_free_gb=100.0,
                active_connections=5,
                response_time_avg_ms=150.0,
                error_rate_percent=2.5
            )
            health_monitor._add_metrics(metrics)
            
        # Should only keep last 3
        assert len(health_monitor.metrics_history) == 3
        assert health_monitor.metrics_history[0].cpu_percent == 2.0
        assert health_monitor.metrics_history[1].cpu_percent == 3.0
        assert health_monitor.metrics_history[2].cpu_percent == 4.0
        
    def test_calculate_performance_metrics_empty_history(self, health_monitor):
        """Test calculating performance metrics with empty history."""
        response_time, error_rate = health_monitor._calculate_performance_metrics()
        
        assert response_time == 0.0
        assert error_rate == 0.0
        
    def test_calculate_performance_metrics(self, health_monitor):
        """Test calculating performance metrics from history."""
        # Add some metrics to history
        base_time = datetime.utcnow()
        for i in range(3):
            metrics = SystemMetrics(
                timestamp=base_time - timedelta(minutes=i),
                cpu_percent=50.0,
                memory_percent=60.0,
                memory_available_gb=8.0,
                disk_usage_percent=70.0,
                disk_free_gb=100.0,
                active_connections=5,
                response_time_avg_ms=100.0 + i * 10,
                error_rate_percent=1.0 + i
            )
            health_monitor.metrics_history.append(metrics)
            
        response_time, error_rate = health_monitor._calculate_performance_metrics()
        
        # Should calculate averages
        assert response_time == 110.0  # (100 + 110 + 120) / 3
        assert error_rate == 2.0  # (1 + 2 + 3) / 3
        
    @pytest.mark.asyncio
    async def test_check_database_health_success(self, health_monitor):
        """Test database health check success."""
        with patch('sqlite3.connect') as mock_connect:
            mock_connection = MagicMock()
            mock_cursor = MagicMock()
            mock_connect.return_value = mock_connection
            mock_connection.cursor.return_value = mock_cursor
            
            await health_monitor._check_database_health()
            
        assert "database" in health_monitor.service_health
        service_health = health_monitor.service_health["database"]
        assert service_health.service_name == "database"
        assert service_health.status in ["healthy", "degraded", "unhealthy"]
        assert service_health.response_time_ms is not None
        
    @pytest.mark.asyncio
    async def test_check_database_health_error(self, health_monitor):
        """Test database health check error."""
        with patch('sqlite3.connect', side_effect=Exception("Database error")):
            await health_monitor._check_database_health()
            
        assert "database" in health_monitor.service_health
        service_health = health_monitor.service_health["database"]
        assert service_health.status == "unhealthy"
        assert service_health.error_message == "Database error"
        
    @pytest.mark.asyncio
    async def test_check_api_health(self, health_monitor):
        """Test API health check."""
        await health_monitor._check_api_health()
        
        assert "api" in health_monitor.service_health
        service_health = health_monitor.service_health["api"]
        assert service_health.service_name == "api"
        assert service_health.status == "healthy"
        
    @pytest.mark.asyncio
    async def test_check_file_system_health(self, health_monitor):
        """Test file system health check."""
        with patch('trading_platform.config.config.validate_paths', return_value=True):
            await health_monitor._check_file_system_health()
            
        assert "filesystem" in health_monitor.service_health
        service_health = health_monitor.service_health["filesystem"]
        assert service_health.service_name == "filesystem"
        assert service_health.status == "healthy"
        
    @pytest.mark.asyncio
    async def test_check_file_system_health_degraded(self, health_monitor):
        """Test file system health check with inaccessible paths."""
        with patch('trading_platform.config.config.validate_paths', return_value=False):
            await health_monitor._check_file_system_health()
            
        assert "filesystem" in health_monitor.service_health
        service_health = health_monitor.service_health["filesystem"]
        assert service_health.status == "degraded"
        assert "SierraChart paths not accessible" in service_health.error_message
        
    def test_get_current_metrics(self, health_monitor):
        """Test getting current metrics."""
        # Empty history
        assert health_monitor.get_current_metrics() is None
        
        # Add a metric
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
        health_monitor._add_metrics(metrics)
        
        current = health_monitor.get_current_metrics()
        assert current == metrics
        
    def test_get_metrics_history(self, health_monitor):
        """Test getting metrics history for time period."""
        base_time = datetime.utcnow()
        
        # Add metrics spanning different time periods
        for i in range(5):
            metrics = SystemMetrics(
                timestamp=base_time - timedelta(minutes=i * 30),
                cpu_percent=50.0,
                memory_percent=60.0,
                memory_available_gb=8.0,
                disk_usage_percent=70.0,
                disk_free_gb=100.0,
                active_connections=5,
                response_time_avg_ms=150.0,
                error_rate_percent=2.5
            )
            health_monitor.metrics_history.append(metrics)
            
        # Get metrics for last 60 minutes
        recent_metrics = health_monitor.get_metrics_history(60)
        
        # Should include metrics from last 60 minutes (first 3 metrics)
        assert len(recent_metrics) == 3
        
    def test_get_overall_health_status(self, health_monitor):
        """Test getting overall health status."""
        # No services
        assert health_monitor.get_overall_health_status() == "unknown"
        
        # All healthy
        health_monitor.service_health["service1"] = ServiceHealth(
            service_name="service1", status="healthy", last_check=datetime.utcnow()
        )
        health_monitor.service_health["service2"] = ServiceHealth(
            service_name="service2", status="healthy", last_check=datetime.utcnow()
        )
        assert health_monitor.get_overall_health_status() == "healthy"
        
        # One degraded
        health_monitor.service_health["service3"] = ServiceHealth(
            service_name="service3", status="degraded", last_check=datetime.utcnow()
        )
        assert health_monitor.get_overall_health_status() == "degraded"
        
        # One unhealthy
        health_monitor.service_health["service4"] = ServiceHealth(
            service_name="service4", status="unhealthy", last_check=datetime.utcnow()
        )
        assert health_monitor.get_overall_health_status() == "unhealthy"
        
    def test_is_healthy(self, health_monitor):
        """Test is_healthy method."""
        # No services
        assert not health_monitor.is_healthy()
        
        # All healthy
        health_monitor.service_health["service1"] = ServiceHealth(
            service_name="service1", status="healthy", last_check=datetime.utcnow()
        )
        assert health_monitor.is_healthy()
        
        # One degraded
        health_monitor.service_health["service2"] = ServiceHealth(
            service_name="service2", status="degraded", last_check=datetime.utcnow()
        )
        assert not health_monitor.is_healthy()
        
    def test_get_health_summary(self, health_monitor):
        """Test getting comprehensive health summary."""
        # Add a metric
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
        health_monitor._add_metrics(metrics)
        
        # Add service health
        health_monitor.service_health["database"] = ServiceHealth(
            service_name="database", status="healthy", last_check=datetime.utcnow()
        )
        
        summary = health_monitor.get_health_summary()
        
        assert "overall_status" in summary
        assert "timestamp" in summary
        assert "system_metrics" in summary
        assert "services" in summary
        assert "uptime_status" in summary
        
        assert summary["system_metrics"]["cpu_percent"] == 50.0
        assert "database" in summary["services"]
        assert summary["services"]["database"]["status"] == "healthy"
        assert summary["uptime_status"] == "stopped"


if __name__ == "__main__":
    pytest.main([__file__])