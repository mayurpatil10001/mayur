"""
Metrics collection service for API endpoints and business operations.

Collects and aggregates metrics for response times, request counts,
error rates, and business-specific metrics.

Requirements: 8.1, 8.3
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import threading
from enum import Enum


logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics we collect."""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    TIMER = "timer"


@dataclass
class MetricData:
    """Individual metric data point."""
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    metric_type: MetricType
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "value": self.value,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "type": self.metric_type.value
        }


@dataclass
class EndpointMetrics:
    """Metrics for a specific API endpoint."""
    endpoint: str
    method: str
    total_requests: int
    success_requests: int
    error_requests: int
    total_response_time: float
    min_response_time: float
    max_response_time: float
    last_request_time: datetime
    
    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        return self.total_response_time / self.total_requests if self.total_requests > 0 else 0.0
        
    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        return (self.error_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0
        
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        return (self.success_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "total_requests": self.total_requests,
            "success_requests": self.success_requests,
            "error_requests": self.error_requests,
            "avg_response_time": self.avg_response_time,
            "min_response_time": self.min_response_time,
            "max_response_time": self.max_response_time,
            "error_rate": self.error_rate,
            "success_rate": self.success_rate,
            "last_request_time": self.last_request_time.isoformat()
        }


class MetricsCollector:
    """Service for collecting and aggregating system metrics."""
    
    def __init__(self):
        self.metrics: List[MetricData] = []
        self.endpoint_metrics: Dict[str, EndpointMetrics] = {}
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, List[float]] = defaultdict(list)
        self.timers: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
        self.max_metrics_history = 10000
        
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None, 
                     metric_type: MetricType = MetricType.GAUGE) -> None:
        """Record a metric value."""
        with self.lock:
            metric = MetricData(
                name=name,
                value=value,
                labels=labels or {},
                timestamp=datetime.utcnow(),
                metric_type=metric_type
            )
            
            self.metrics.append(metric)
            
            # Store in appropriate collection
            if metric_type == MetricType.COUNTER:
                self.counters[name] += value
            elif metric_type == MetricType.GAUGE:
                self.gauges[name] = value
            elif metric_type == MetricType.HISTOGRAM:
                self.histograms[name].append(value)
            elif metric_type == MetricType.TIMER:
                self.timers[name].append(value)
                
            # Trim metrics history if too large
            if len(self.metrics) > self.max_metrics_history:
                self.metrics = self.metrics[-self.max_metrics_history:]
                
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        self.record_metric(name, value, labels, MetricType.COUNTER)
        
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        self.record_metric(name, value, labels, MetricType.GAUGE)
        
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        self.record_metric(name, value, labels, MetricType.HISTOGRAM)
        
    def record_timer(self, name: str, duration: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a timer duration in seconds."""
        self.record_metric(name, duration * 1000, labels, MetricType.TIMER)  # Convert to ms
        
    def record_request_metrics(self, endpoint: str, method: str, response_time: float, 
                             status_code: int) -> None:
        """Record metrics for an API request."""
        with self.lock:
            key = f"{method}:{endpoint}"
            
            if key not in self.endpoint_metrics:
                self.endpoint_metrics[key] = EndpointMetrics(
                    endpoint=endpoint,
                    method=method,
                    total_requests=0,
                    success_requests=0,
                    error_requests=0,
                    total_response_time=0.0,
                    min_response_time=float('inf'),
                    max_response_time=0.0,
                    last_request_time=datetime.utcnow()
                )
                
            metrics = self.endpoint_metrics[key]
            metrics.total_requests += 1
            metrics.total_response_time += response_time
            metrics.min_response_time = min(metrics.min_response_time, response_time)
            metrics.max_response_time = max(metrics.max_response_time, response_time)
            metrics.last_request_time = datetime.utcnow()
            
            if 200 <= status_code < 300:
                metrics.success_requests += 1
            else:
                metrics.error_requests += 1
                
        # Record individual metrics
        labels = {"endpoint": endpoint, "method": method, "status": str(status_code)}
        self.increment_counter("http_requests_total", 1.0, labels)
        self.record_timer("http_request_duration", response_time, labels)
        
        if status_code >= 400:
            self.increment_counter("http_errors_total", 1.0, labels)
            
    def record_business_metric(self, metric_name: str, value: float, 
                             labels: Optional[Dict[str, str]] = None) -> None:
        """Record business-specific metrics."""
        self.record_metric(f"business_{metric_name}", value, labels, MetricType.GAUGE)
        
    def record_trade_metrics(self, account: str, symbol: str, profit_loss: float, 
                           duration_minutes: float) -> None:
        """Record trading-specific metrics."""
        labels = {"account": account, "symbol": symbol}
        
        self.increment_counter("trades_total", 1.0, labels)
        self.record_histogram("trade_pnl", profit_loss, labels)
        self.record_histogram("trade_duration_minutes", duration_minutes, labels)
        
        if profit_loss > 0:
            self.increment_counter("winning_trades_total", 1.0, labels)
        else:
            self.increment_counter("losing_trades_total", 1.0, labels)
            
    def record_recommendation_metrics(self, account: str, symbol: str, confidence: float,
                                    action: str, strategy: str) -> None:
        """Record recommendation-specific metrics."""
        labels = {
            "account": account, 
            "symbol": symbol, 
            "action": action,
            "strategy": strategy
        }
        
        self.increment_counter("recommendations_total", 1.0, labels)
        self.record_histogram("recommendation_confidence", confidence, labels)
        
    def get_endpoint_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all API endpoints."""
        with self.lock:
            return {key: metrics.to_dict() for key, metrics in self.endpoint_metrics.items()}
            
    def get_counter_values(self) -> Dict[str, float]:
        """Get current counter values."""
        with self.lock:
            return dict(self.counters)
            
    def get_gauge_values(self) -> Dict[str, float]:
        """Get current gauge values."""
        with self.lock:
            return dict(self.gauges)
            
    def get_histogram_stats(self) -> Dict[str, Dict[str, float]]:
        """Get histogram statistics."""
        with self.lock:
            stats = {}
            for name, values in self.histograms.items():
                if values:
                    sorted_values = sorted(values)
                    n = len(sorted_values)
                    stats[name] = {
                        "count": n,
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "mean": sum(values) / n,
                        "p50": sorted_values[int(n * 0.5)],
                        "p95": sorted_values[int(n * 0.95)],
                        "p99": sorted_values[int(n * 0.99)]
                    }
            return stats
            
    def get_timer_stats(self) -> Dict[str, Dict[str, float]]:
        """Get timer statistics."""
        with self.lock:
            stats = {}
            for name, durations in self.timers.items():
                if durations:
                    sorted_durations = sorted(durations)
                    n = len(sorted_durations)
                    stats[name] = {
                        "count": n,
                        "sum_ms": sum(durations),
                        "min_ms": min(durations),
                        "max_ms": max(durations),
                        "mean_ms": sum(durations) / n,
                        "p50_ms": sorted_durations[int(n * 0.5)],
                        "p95_ms": sorted_durations[int(n * 0.95)],
                        "p99_ms": sorted_durations[int(n * 0.99)]
                    }
            return stats
            
    def get_metrics_for_period(self, minutes: int = 60) -> List[Dict[str, Any]]:
        """Get metrics for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        with self.lock:
            return [
                metric.to_dict() 
                for metric in self.metrics 
                if metric.timestamp > cutoff_time
            ]
            
    def get_prometheus_metrics(self) -> str:
        """Generate Prometheus-format metrics."""
        lines = []
        
        # Counters
        for name, value in self.get_counter_values().items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")
            
        # Gauges
        for name, value in self.get_gauge_values().items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
            
        # Histograms
        for name, stats in self.get_histogram_stats().items():
            lines.append(f"# TYPE {name} histogram")
            for stat, value in stats.items():
                lines.append(f"{name}_{stat} {value}")
                
        # Timers (as histograms)
        for name, stats in self.get_timer_stats().items():
            lines.append(f"# TYPE {name} histogram")
            for stat, value in stats.items():
                lines.append(f"{name}_{stat} {value}")
                
        return "\n".join(lines)
        
    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive metrics summary."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_metrics_count": len(self.metrics),
            "endpoints": self.get_endpoint_metrics(),
            "counters": self.get_counter_values(),
            "gauges": self.get_gauge_values(),
            "histograms": self.get_histogram_stats(),
            "timers": self.get_timer_stats()
        }
        
    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self.lock:
            self.metrics.clear()
            self.endpoint_metrics.clear()
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
            self.timers.clear()


# Global metrics collector instance
metrics_collector = MetricsCollector()