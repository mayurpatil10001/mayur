"""
Tests for the metrics collection service.

Tests metrics collection, aggregation, and reporting functionality.

Requirements: 8.1, 8.3
"""

import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import patch

from trading_platform.services.monitoring.metrics_collector import (
    MetricsCollector,
    MetricData,
    EndpointMetrics,
    MetricType
)


class TestMetricData:
    """Test MetricData dataclass."""
    
    def test_to_dict(self):
        """Test converting MetricData to dictionary."""
        metric = MetricData(
            name="test_metric",
            value=123.45,
            labels={"service": "api", "endpoint": "/test"},
            timestamp=datetime(2024, 1, 1, 12, 0, 0),
            metric_type=MetricType.GAUGE
        )
        
        result = metric.to_dict()
        
        assert result['name'] == "test_metric"
        assert result['value'] == 123.45
        assert result['labels'] == {"service": "api", "endpoint": "/test"}
        assert result['timestamp'] == '2024-01-01T12:00:00'
        assert result['type'] == "gauge"


class TestEndpointMetrics:
    """Test EndpointMetrics dataclass."""
    
    def test_properties(self):
        """Test EndpointMetrics calculated properties."""
        metrics = EndpointMetrics(
            endpoint="/api/test",
            method="GET",
            total_requests=100,
            success_requests=80,
            error_requests=20,
            total_response_time=5000.0,
            min_response_time=10.0,
            max_response_time=500.0,
            last_request_time=datetime.utcnow()
        )
        
        assert metrics.avg_response_time == 50.0  # 5000 / 100
        assert metrics.error_rate == 20.0  # 20 / 100 * 100
        assert metrics.success_rate == 80.0  # 80 / 100 * 100
        
    def test_properties_zero_requests(self):
        """Test properties with zero requests."""
        metrics = EndpointMetrics(
            endpoint="/api/test",
            method="GET",
            total_requests=0,
            success_requests=0,
            error_requests=0,
            total_response_time=0.0,
            min_response_time=0.0,
            max_response_time=0.0,
            last_request_time=datetime.utcnow()
        )
        
        assert metrics.avg_response_time == 0.0
        assert metrics.error_rate == 0.0
        assert metrics.success_rate == 0.0
        
    def test_to_dict(self):
        """Test converting EndpointMetrics to dictionary."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0)
        metrics = EndpointMetrics(
            endpoint="/api/test",
            method="GET",
            total_requests=100,
            success_requests=80,
            error_requests=20,
            total_response_time=5000.0,
            min_response_time=10.0,
            max_response_time=500.0,
            last_request_time=timestamp
        )
        
        result = metrics.to_dict()
        
        assert result['endpoint'] == "/api/test"
        assert result['method'] == "GET"
        assert result['total_requests'] == 100
        assert result['avg_response_time'] == 50.0
        assert result['error_rate'] == 20.0
        assert result['success_rate'] == 80.0
        assert result['last_request_time'] == '2024-01-01T12:00:00'


class TestMetricsCollector:
    """Test MetricsCollector."""
    
    @pytest.fixture
    def collector(self):
        """Create metrics collector instance for testing."""
        collector = MetricsCollector()
        collector.reset_metrics()  # Start with clean state
        return collector
        
    def test_initialization(self, collector):
        """Test metrics collector initialization."""
        assert collector.metrics == []
        assert collector.endpoint_metrics == {}
        assert collector.counters == {}
        assert collector.gauges == {}
        assert collector.histograms == {}
        assert collector.timers == {}
        assert collector.max_metrics_history == 10000
        
    def test_record_metric(self, collector):
        """Test recording a basic metric."""
        labels = {"service": "api"}
        collector.record_metric("test_metric", 123.45, labels, MetricType.GAUGE)
        
        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.name == "test_metric"
        assert metric.value == 123.45
        assert metric.labels == labels
        assert metric.metric_type == MetricType.GAUGE
        
        # Should be stored in gauges
        assert collector.gauges["test_metric"] == 123.45
        
    def test_record_metric_no_labels(self, collector):
        """Test recording a metric without labels."""
        collector.record_metric("test_metric", 100.0)
        
        assert len(collector.metrics) == 1
        assert collector.metrics[0].labels == {}
        
    def test_increment_counter(self, collector):
        """Test incrementing a counter metric."""
        collector.increment_counter("requests_total", 1.0)
        collector.increment_counter("requests_total", 2.0)
        
        assert len(collector.metrics) == 2
        assert collector.counters["requests_total"] == 3.0
        
    def test_set_gauge(self, collector):
        """Test setting a gauge metric."""
        collector.set_gauge("cpu_usage", 50.0)
        collector.set_gauge("cpu_usage", 60.0)  # Update value
        
        assert len(collector.metrics) == 2
        assert collector.gauges["cpu_usage"] == 60.0
        
    def test_record_histogram(self, collector):
        """Test recording histogram values."""
        collector.record_histogram("response_time", 100.0)
        collector.record_histogram("response_time", 150.0)
        collector.record_histogram("response_time", 200.0)
        
        assert len(collector.metrics) == 3
        assert collector.histograms["response_time"] == [100.0, 150.0, 200.0]
        
    def test_record_timer(self, collector):
        """Test recording timer durations."""
        collector.record_timer("api_duration", 0.5)  # 0.5 seconds
        collector.record_timer("api_duration", 1.0)  # 1.0 seconds
        
        assert len(collector.metrics) == 2
        # Should convert to milliseconds
        assert collector.timers["api_duration"] == [500.0, 1000.0]
        
    def test_record_request_metrics(self, collector):
        """Test recording API request metrics."""
        collector.record_request_metrics("/api/test", "GET", 150.0, 200)
        collector.record_request_metrics("/api/test", "GET", 100.0, 404)
        
        # Should create endpoint metrics
        key = "GET:/api/test"
        assert key in collector.endpoint_metrics
        
        metrics = collector.endpoint_metrics[key]
        assert metrics.endpoint == "/api/test"
        assert metrics.method == "GET"
        assert metrics.total_requests == 2
        assert metrics.success_requests == 1
        assert metrics.error_requests == 1
        assert metrics.total_response_time == 250.0
        assert metrics.avg_response_time == 125.0
        
        # Should also record individual metrics
        assert collector.counters["http_requests_total"] == 2.0
        assert collector.counters["http_errors_total"] == 1.0
        
    def test_record_business_metric(self, collector):
        """Test recording business-specific metrics."""
        labels = {"account": "test_account"}
        collector.record_business_metric("profit_factor", 1.5, labels)
        
        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.name == "business_profit_factor"
        assert metric.value == 1.5
        assert metric.labels == labels
        
    def test_record_trade_metrics(self, collector):
        """Test recording trading-specific metrics."""
        collector.record_trade_metrics("TEST_ACCOUNT", "NQ", 250.0, 45.0)
        collector.record_trade_metrics("TEST_ACCOUNT", "NQ", -100.0, 30.0)
        
        # Should record multiple metrics
        assert collector.counters["trades_total"] == 2.0
        assert collector.counters["winning_trades_total"] == 1.0
        assert collector.counters["losing_trades_total"] == 1.0
        assert collector.histograms["trade_pnl"] == [250.0, -100.0]
        assert collector.histograms["trade_duration_minutes"] == [45.0, 30.0]
        
    def test_record_recommendation_metrics(self, collector):
        """Test recording recommendation-specific metrics."""
        collector.record_recommendation_metrics(
            "TEST_ACCOUNT", "NQ", 0.85, "TRADE", "ML"
        )
        
        assert collector.counters["recommendations_total"] == 1.0
        assert collector.histograms["recommendation_confidence"] == [0.85]
        
    def test_get_endpoint_metrics(self, collector):
        """Test getting endpoint metrics."""
        collector.record_request_metrics("/api/test", "GET", 150.0, 200)
        
        metrics = collector.get_endpoint_metrics()
        
        assert "GET:/api/test" in metrics
        endpoint_data = metrics["GET:/api/test"]
        assert endpoint_data["endpoint"] == "/api/test"
        assert endpoint_data["method"] == "GET"
        assert endpoint_data["total_requests"] == 1
        
    def test_get_counter_values(self, collector):
        """Test getting counter values."""
        collector.increment_counter("test_counter", 5.0)
        
        counters = collector.get_counter_values()
        
        assert counters["test_counter"] == 5.0
        
    def test_get_gauge_values(self, collector):
        """Test getting gauge values."""
        collector.set_gauge("test_gauge", 42.0)
        
        gauges = collector.get_gauge_values()
        
        assert gauges["test_gauge"] == 42.0
        
    def test_get_histogram_stats(self, collector):
        """Test getting histogram statistics."""
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for value in values:
            collector.record_histogram("test_histogram", value)
            
        stats = collector.get_histogram_stats()
        
        assert "test_histogram" in stats
        hist_stats = stats["test_histogram"]
        assert hist_stats["count"] == 5
        assert hist_stats["sum"] == 150.0
        assert hist_stats["min"] == 10.0
        assert hist_stats["max"] == 50.0
        assert hist_stats["mean"] == 30.0
        assert hist_stats["p50"] == 30.0
        
    def test_get_timer_stats(self, collector):
        """Test getting timer statistics."""
        durations = [100.0, 200.0, 300.0, 400.0, 500.0]  # milliseconds
        for duration in durations:
            collector.record_timer("test_timer", duration / 1000)  # Convert to seconds
            
        stats = collector.get_timer_stats()
        
        assert "test_timer" in stats
        timer_stats = stats["test_timer"]
        assert timer_stats["count"] == 5
        assert timer_stats["sum_ms"] == 1500.0
        assert timer_stats["min_ms"] == 100.0
        assert timer_stats["max_ms"] == 500.0
        assert timer_stats["mean_ms"] == 300.0
        
    def test_get_metrics_for_period(self, collector):
        """Test getting metrics for time period."""
        base_time = datetime.utcnow()
        
        # Add metrics at different times
        with patch('trading_platform.services.monitoring.metrics_collector.datetime') as mock_datetime:
            # Old metric (2 hours ago)
            mock_datetime.utcnow.return_value = base_time - timedelta(hours=2)
            collector.record_metric("old_metric", 1.0)
            
            # Recent metric (30 minutes ago)
            mock_datetime.utcnow.return_value = base_time - timedelta(minutes=30)
            collector.record_metric("recent_metric", 2.0)
            
            # Current metric
            mock_datetime.utcnow.return_value = base_time
            collector.record_metric("current_metric", 3.0)
            
        # Get metrics for last 60 minutes
        recent_metrics = collector.get_metrics_for_period(60)
        
        # Should include recent and current metrics
        assert len(recent_metrics) == 2
        names = [m['name'] for m in recent_metrics]
        assert "recent_metric" in names
        assert "current_metric" in names
        assert "old_metric" not in names
        
    def test_get_prometheus_metrics(self, collector):
        """Test generating Prometheus format metrics."""
        collector.increment_counter("http_requests_total", 100.0)
        collector.set_gauge("cpu_usage_percent", 75.0)
        collector.record_histogram("response_time_ms", 150.0)
        collector.record_timer("api_duration", 0.5)
        
        prometheus_output = collector.get_prometheus_metrics()
        
        assert "# TYPE http_requests_total counter" in prometheus_output
        assert "http_requests_total 100" in prometheus_output
        assert "# TYPE cpu_usage_percent gauge" in prometheus_output
        assert "cpu_usage_percent 75" in prometheus_output
        assert "# TYPE response_time_ms histogram" in prometheus_output
        assert "# TYPE api_duration histogram" in prometheus_output
        
    def test_get_summary(self, collector):
        """Test getting comprehensive metrics summary."""
        collector.increment_counter("test_counter", 1.0)
        collector.set_gauge("test_gauge", 50.0)
        collector.record_request_metrics("/api/test", "GET", 100.0, 200)
        
        summary = collector.get_summary()
        
        assert "timestamp" in summary
        assert "total_metrics_count" in summary
        assert "endpoints" in summary
        assert "counters" in summary
        assert "gauges" in summary
        assert "histograms" in summary
        assert "timers" in summary
        
        assert summary["counters"]["test_counter"] == 1.0
        assert summary["gauges"]["test_gauge"] == 50.0
        assert "GET:/api/test" in summary["endpoints"]
        
    def test_reset_metrics(self, collector):
        """Test resetting all metrics."""
        # Add some metrics
        collector.increment_counter("test_counter", 1.0)
        collector.set_gauge("test_gauge", 50.0)
        collector.record_request_metrics("/api/test", "GET", 100.0, 200)
        
        # Verify metrics exist
        assert len(collector.metrics) > 0
        assert len(collector.counters) > 0
        
        # Reset
        collector.reset_metrics()
        
        # Verify everything is cleared
        assert len(collector.metrics) == 0
        assert len(collector.endpoint_metrics) == 0
        assert len(collector.counters) == 0
        assert len(collector.gauges) == 0
        assert len(collector.histograms) == 0
        assert len(collector.timers) == 0
        
    def test_metrics_history_limit(self, collector):
        """Test that metrics history is limited."""
        collector.max_metrics_history = 5
        
        # Add more metrics than limit
        for i in range(10):
            collector.record_metric(f"metric_{i}", float(i))
            
        # Should only keep last 5
        assert len(collector.metrics) == 5
        
        # Should keep metrics 5-9
        names = [m.name for m in collector.metrics]
        assert "metric_5" in names
        assert "metric_9" in names
        assert "metric_0" not in names
        assert "metric_4" not in names


if __name__ == "__main__":
    pytest.main([__file__])