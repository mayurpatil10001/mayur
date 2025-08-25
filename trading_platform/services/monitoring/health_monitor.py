"""
System health monitoring service.

Monitors system performance metrics including CPU usage, memory consumption,
database connectivity, and service availability.

Requirements: 8.1, 8.3
"""

import psutil
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3

from ...config import config
from ...api.dependencies import get_database_session


logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System performance metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    active_connections: int
    response_time_avg_ms: float
    error_rate_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ServiceHealth:
    """Service health status."""
    service_name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None
    uptime_percent: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['last_check'] = self.last_check.isoformat()
        return data


class HealthMonitorService:
    """Service for monitoring system health and performance."""
    
    def __init__(self):
        self.metrics_history: List[SystemMetrics] = []
        self.service_health: Dict[str, ServiceHealth] = {}
        self.max_history_size = 1000  # Keep last 1000 metrics
        self.check_interval = 30  # Check every 30 seconds
        self.is_monitoring = False
        
    async def start_monitoring(self) -> None:
        """Start continuous monitoring."""
        if self.is_monitoring:
            logger.warning("Monitoring is already running")
            return
            
        self.is_monitoring = True
        logger.info("Starting health monitoring service")
        
        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())
        
    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self.is_monitoring = False
        logger.info("Stopped health monitoring service")
        
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self.is_monitoring:
            try:
                # Collect system metrics
                metrics = await self._collect_system_metrics()
                self._add_metrics(metrics)
                
                # Check service health
                await self._check_service_health()
                
                # Wait for next interval
                await asyncio.sleep(self.check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.check_interval)
                
    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_gb = memory.available / (1024**3)
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_free_gb = disk.free / (1024**3)
            
            # Database connections (approximate)
            active_connections = await self._get_active_connections()
            
            # Response time and error rate (from recent history)
            response_time_avg, error_rate = self._calculate_performance_metrics()
            
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_gb=memory_available_gb,
                disk_usage_percent=disk_usage_percent,
                disk_free_gb=disk_free_gb,
                active_connections=active_connections,
                response_time_avg_ms=response_time_avg,
                error_rate_percent=error_rate
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            # Return default metrics on error
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_gb=0.0,
                disk_usage_percent=0.0,
                disk_free_gb=0.0,
                active_connections=0,
                response_time_avg_ms=0.0,
                error_rate_percent=100.0
            )
            
    async def _get_active_connections(self) -> int:
        """Get number of active database connections."""
        try:
            # For SQLite, we can check if the database file is locked
            # This is a simplified check
            db_path = config.DATABASE_URL.replace('sqlite:///', '')
            if Path(db_path).exists():
                return 1  # SQLite typically has one connection
            return 0
        except Exception:
            return 0
            
    def _calculate_performance_metrics(self) -> tuple[float, float]:
        """Calculate average response time and error rate from recent metrics."""
        if not self.metrics_history:
            return 0.0, 0.0
            
        # Get metrics from last 5 minutes
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
        if not recent_metrics:
            return 0.0, 0.0
            
        # Calculate averages
        avg_response_time = sum(m.response_time_avg_ms for m in recent_metrics) / len(recent_metrics)
        avg_error_rate = sum(m.error_rate_percent for m in recent_metrics) / len(recent_metrics)
        
        return avg_response_time, avg_error_rate
        
    def _add_metrics(self, metrics: SystemMetrics) -> None:
        """Add metrics to history, maintaining size limit."""
        self.metrics_history.append(metrics)
        
        # Trim history if too large
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
            
    async def _check_service_health(self) -> None:
        """Check health of all services."""
        await self._check_database_health()
        await self._check_api_health()
        await self._check_file_system_health()
        
    async def _check_database_health(self) -> None:
        """Check database connectivity and performance."""
        service_name = "database"
        start_time = time.time()
        
        try:
            # Test database connection using sync connection for simplicity
            db_path = config.DATABASE_URL.replace('sqlite:///', '')
            connection = sqlite3.connect(db_path)
            cursor = connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            connection.close()
                
            response_time = (time.time() - start_time) * 1000
            
            # Determine status based on response time
            if response_time < 100:
                status = "healthy"
            elif response_time < 500:
                status = "degraded"
            else:
                status = "unhealthy"
                
            self.service_health[service_name] = ServiceHealth(
                service_name=service_name,
                status=status,
                last_check=datetime.utcnow(),
                response_time_ms=response_time
            )
            
        except Exception as e:
            self.service_health[service_name] = ServiceHealth(
                service_name=service_name,
                status="unhealthy",
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
            
    async def _check_api_health(self) -> None:
        """Check API service health."""
        service_name = "api"
        
        try:
            # For now, assume API is healthy if we're running
            # In a real implementation, this would check API endpoints
            self.service_health[service_name] = ServiceHealth(
                service_name=service_name,
                status="healthy",
                last_check=datetime.utcnow(),
                response_time_ms=50.0
            )
            
        except Exception as e:
            self.service_health[service_name] = ServiceHealth(
                service_name=service_name,
                status="unhealthy", 
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
            
    async def _check_file_system_health(self) -> None:
        """Check file system accessibility."""
        service_name = "filesystem"
        
        try:
            # Check if SierraChart paths are accessible
            paths_accessible = config.validate_paths()
            
            status = "healthy" if paths_accessible else "degraded"
            
            self.service_health[service_name] = ServiceHealth(
                service_name=service_name,
                status=status,
                last_check=datetime.utcnow(),
                error_message=None if paths_accessible else "SierraChart paths not accessible"
            )
            
        except Exception as e:
            self.service_health[service_name] = ServiceHealth(
                service_name=service_name,
                status="unhealthy",
                last_check=datetime.utcnow(),
                error_message=str(e)
            )
            
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get the most recent system metrics."""
        return self.metrics_history[-1] if self.metrics_history else None
        
    def get_metrics_history(self, minutes: int = 60) -> List[SystemMetrics]:
        """Get metrics history for the specified time period."""
        cutoff_time = datetime.utcnow() - timedelta(minutes=minutes)
        return [m for m in self.metrics_history if m.timestamp > cutoff_time]
        
    def get_service_health_status(self) -> Dict[str, ServiceHealth]:
        """Get current health status of all services."""
        return self.service_health.copy()
        
    def get_overall_health_status(self) -> str:
        """Get overall system health status."""
        if not self.service_health:
            return "unknown"
            
        statuses = [service.status for service in self.service_health.values()]
        
        if "unhealthy" in statuses:
            return "unhealthy"
        elif "degraded" in statuses:
            return "degraded"
        else:
            return "healthy"
            
    def is_healthy(self) -> bool:
        """Check if system is currently healthy."""
        return self.get_overall_health_status() == "healthy"
        
    def get_health_summary(self) -> Dict[str, Any]:
        """Get comprehensive health summary."""
        current_metrics = self.get_current_metrics()
        
        return {
            "overall_status": self.get_overall_health_status(),
            "timestamp": datetime.utcnow().isoformat(),
            "system_metrics": current_metrics.to_dict() if current_metrics else None,
            "services": {name: service.to_dict() for name, service in self.service_health.items()},
            "uptime_status": "running" if self.is_monitoring else "stopped"
        }


# Global health monitor instance
health_monitor = HealthMonitorService()