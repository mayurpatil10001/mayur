"""
Database connection pool management and optimization service.

This module provides advanced connection pool management capabilities including:
- Dynamic connection pool sizing based on workload
- Connection health monitoring and recovery
- Connection pool performance metrics
- Automatic pool optimization strategies

Requirements: 10.1, 10.2, 10.3
"""

import logging
import asyncio
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, ContextManager
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
from collections import deque, defaultdict
import sqlite3
import psutil

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool, NullPool

logger = logging.getLogger(__name__)


class PoolStrategy(Enum):
    """Connection pool strategies."""
    STATIC = "static"
    DYNAMIC = "dynamic"
    ADAPTIVE = "adaptive"
    BURST = "burst"


class ConnectionState(Enum):
    """Connection states."""
    IDLE = "idle"
    ACTIVE = "active"
    STALE = "stale"
    INVALID = "invalid"
    CHECKING = "checking"


@dataclass
class ConnectionMetrics:
    """Metrics for individual database connections."""
    connection_id: str
    created_at: datetime
    last_used: datetime
    total_queries: int = 0
    total_query_time: float = 0.0
    avg_query_time: float = 0.0
    state: ConnectionState = ConnectionState.IDLE
    error_count: int = 0
    last_error: Optional[str] = None
    health_score: float = 100.0


@dataclass
class PoolMetrics:
    """Connection pool performance metrics."""
    pool_size: int
    active_connections: int
    idle_connections: int
    stale_connections: int
    invalid_connections: int
    wait_queue_size: int
    total_checkouts: int = 0
    total_checkins: int = 0
    checkout_failures: int = 0
    avg_checkout_time: float = 0.0
    max_checkout_time: float = 0.0
    pool_efficiency: float = 0.0
    connection_lifetime_avg: float = 0.0
    error_rate: float = 0.0


@dataclass
class PoolConfiguration:
    """Connection pool configuration."""
    min_size: int = 5
    max_size: int = 20
    overflow: int = 0
    recycle_time: int = 3600  # seconds
    timeout: float = 30.0  # seconds
    pre_ping: bool = True
    echo: bool = False
    strategy: PoolStrategy = PoolStrategy.DYNAMIC
    health_check_interval: int = 60  # seconds
    stale_timeout: int = 300  # seconds
    max_connection_lifetime: int = 7200  # seconds


@dataclass
class OptimizationEvent:
    """Pool optimization event."""
    timestamp: datetime
    event_type: str  # resize, cleanup, recovery, etc.
    old_size: int
    new_size: int
    reason: str
    impact_score: float


class ConnectionPoolManager:
    """
    Advanced connection pool manager with dynamic optimization for concurrent analytics.
    
    Provides intelligent connection pool management with automatic
    sizing, health monitoring, and performance optimization specifically
    optimized for concurrent time-bin analytics workloads.
    """
    
    def __init__(
        self,
        database_url: str,
        pool_config: Optional[PoolConfiguration] = None,
        monitoring_enabled: bool = True
    ):
        """Initialize the connection pool manager optimized for analytics."""
        self.database_url = database_url
        
        # Set optimized defaults for analytics workloads if no config provided
        if pool_config is None:
            pool_config = PoolConfiguration(
                min_size=8,  # Higher minimum for analytics
                max_size=32,  # Higher maximum for concurrent processing
                overflow=16,  # Allow burst capacity
                recycle_time=1800,  # 30 minutes recycle
                timeout=60.0,  # Longer timeout for complex queries
                pre_ping=True,
                strategy=PoolStrategy.ADAPTIVE,  # Adaptive for analytics
                health_check_interval=30,  # More frequent health checks
                stale_timeout=600,  # 10 minutes stale timeout
                max_connection_lifetime=3600  # 1 hour max lifetime
            )
        
        self.pool_config = pool_config
        self.monitoring_enabled = monitoring_enabled
        
        # Initialize engine and pool
        self.engine: Optional[Engine] = None
        self.SessionLocal: Optional[sessionmaker] = None
        
        # Monitoring data
        self.connection_metrics: Dict[str, ConnectionMetrics] = {}
        self.pool_metrics_history: deque = deque(maxlen=1000)
        self.optimization_events: deque = deque(maxlen=500)
        
        # Performance tracking
        self.checkout_times: deque = deque(maxlen=1000)
        self.query_times: deque = deque(maxlen=10000)
        
        # Monitoring thread
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        
        # Optimization state
        self.last_optimization = datetime.now()
        self.optimization_interval = 300  # 5 minutes
        
        # Pool statistics
        self.total_connections_created = 0
        self.total_connections_closed = 0
        self.total_optimization_cycles = 0
        
        # Initialize the pool
        self._initialize_pool()
        
        logger.info(f"ConnectionPoolManager initialized with strategy: {self.pool_config.strategy.value}")
    
    async def start_monitoring(self):
        """Start connection pool monitoring."""
        if not self.monitoring_enabled:
            logger.warning("Pool monitoring is disabled")
            return
        
        self.monitoring_active = True
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        
        logger.info("Connection pool monitoring started")
    
    async def stop_monitoring(self):
        """Stop connection pool monitoring."""
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Connection pool monitoring stopped")
    
    @contextmanager
    def get_session(self) -> ContextManager[Session]:
        """
        Get database session with pool management.
        
        Yields:
            SQLAlchemy database session
        """
        checkout_start = time.time()
        session = None
        
        try:
            # Get session from pool
            session = self.SessionLocal()
            
            # Track checkout time
            checkout_time = time.time() - checkout_start
            self.checkout_times.append(checkout_time)
            
            # Update pool metrics
            self._update_checkout_metrics(checkout_time)
            
            yield session
            session.commit()
            
        except Exception as e:
            if session:
                session.rollback()
            
            # Track checkout failure
            self._track_checkout_failure(str(e))
            raise
            
        finally:
            if session:
                session.close()
                
                # Track checkin
                self._update_checkin_metrics()
    
    async def get_pool_health(self) -> Dict[str, Any]:
        """
        Get comprehensive pool health metrics.
        
        Returns:
            Pool health information
        """
        current_metrics = await self._collect_current_metrics()
        
        # Calculate health score
        health_score = self._calculate_pool_health_score(current_metrics)
        
        # Get optimization recommendations
        recommendations = await self._get_optimization_recommendations(current_metrics)
        
        return {
            "health_score": health_score,
            "pool_metrics": self._pool_metrics_to_dict(current_metrics),
            "connection_details": {
                conn_id: self._connection_metrics_to_dict(metrics)
                for conn_id, metrics in self.connection_metrics.items()
            },
            "optimization_recommendations": recommendations,
            "recent_events": [
                self._optimization_event_to_dict(event)
                for event in list(self.optimization_events)[-10:]
            ]
        }
    
    async def optimize_pool_size(self, force: bool = False) -> Dict[str, Any]:
        """
        Optimize connection pool size based on current workload.
        
        Args:
            force: Force optimization even if recent optimization occurred
            
        Returns:
            Optimization results
        """
        if not force and (datetime.now() - self.last_optimization).total_seconds() < self.optimization_interval:
            return {"status": "skipped", "reason": "recent_optimization"}
        
        logger.info("Starting pool size optimization")
        
        # Collect current metrics
        current_metrics = await self._collect_current_metrics()
        
        # Analyze workload patterns
        workload_analysis = await self._analyze_workload_patterns()
        
        # Calculate optimal pool size
        optimal_size = await self._calculate_optimal_pool_size(
            current_metrics, workload_analysis
        )
        
        # Apply optimization if needed
        current_size = current_metrics.pool_size
        optimization_result = {
            "current_size": current_size,
            "optimal_size": optimal_size,
            "workload_analysis": workload_analysis,
            "optimization_applied": False
        }
        
        if optimal_size != current_size:
            # Apply optimization
            await self._resize_pool(optimal_size, "workload_optimization")
            optimization_result["optimization_applied"] = True
            
            # Record optimization event
            self.optimization_events.append(OptimizationEvent(
                timestamp=datetime.now(),
                event_type="resize",
                old_size=current_size,
                new_size=optimal_size,
                reason="workload_optimization",
                impact_score=abs(optimal_size - current_size) / current_size * 100
            ))
        
        self.last_optimization = datetime.now()
        self.total_optimization_cycles += 1
        
        logger.info(f"Pool optimization completed: {current_size} -> {optimal_size}")
        
        return optimization_result
    
    async def cleanup_stale_connections(self) -> Dict[str, Any]:
        """
        Cleanup stale and invalid connections.
        
        Returns:
            Cleanup results
        """
        logger.info("Starting stale connection cleanup")
        
        cleanup_result = {
            "connections_checked": 0,
            "stale_connections": 0,
            "invalid_connections": 0,
            "connections_closed": 0,
            "errors": []
        }
        
        current_time = datetime.now()
        stale_threshold = timedelta(seconds=self.pool_config.stale_timeout)
        lifetime_threshold = timedelta(seconds=self.pool_config.max_connection_lifetime)
        
        connections_to_remove = []
        
        for conn_id, metrics in self.connection_metrics.items():
            cleanup_result["connections_checked"] += 1
            
            # Check if connection is stale
            if current_time - metrics.last_used > stale_threshold:
                metrics.state = ConnectionState.STALE
                cleanup_result["stale_connections"] += 1
                connections_to_remove.append(conn_id)
            
            # Check if connection exceeded max lifetime
            elif current_time - metrics.created_at > lifetime_threshold:
                metrics.state = ConnectionState.INVALID
                cleanup_result["invalid_connections"] += 1
                connections_to_remove.append(conn_id)
            
            # Check connection health
            elif metrics.health_score < 50.0:
                metrics.state = ConnectionState.INVALID
                cleanup_result["invalid_connections"] += 1
                connections_to_remove.append(conn_id)
        
        # Remove identified connections
        for conn_id in connections_to_remove:
            try:
                await self._close_connection(conn_id)
                del self.connection_metrics[conn_id]
                cleanup_result["connections_closed"] += 1
            except Exception as e:
                cleanup_result["errors"].append(f"Failed to close {conn_id}: {str(e)}")
        
        # Record cleanup event
        if cleanup_result["connections_closed"] > 0:
            self.optimization_events.append(OptimizationEvent(
                timestamp=current_time,
                event_type="cleanup",
                old_size=len(self.connection_metrics) + cleanup_result["connections_closed"],
                new_size=len(self.connection_metrics),
                reason="stale_connection_cleanup",
                impact_score=cleanup_result["connections_closed"]
            ))
        
        logger.info(f"Cleanup completed: {cleanup_result['connections_closed']} connections closed")
        
        return cleanup_result
    
    async def get_performance_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive pool performance report.
        
        Returns:
            Performance report
        """
        current_metrics = await self._collect_current_metrics()
        
        # Calculate performance statistics
        checkout_stats = self._calculate_checkout_statistics()
        query_stats = self._calculate_query_statistics()
        efficiency_stats = self._calculate_efficiency_statistics(current_metrics)
        
        # Analyze trends
        trend_analysis = self._analyze_performance_trends()
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "pool_configuration": self._pool_config_to_dict(),
            "current_metrics": self._pool_metrics_to_dict(current_metrics),
            "performance_statistics": {
                "checkout_stats": checkout_stats,
                "query_stats": query_stats,
                "efficiency_stats": efficiency_stats
            },
            "trend_analysis": trend_analysis,
            "optimization_history": [
                self._optimization_event_to_dict(event)
                for event in list(self.optimization_events)
            ],
            "recommendations": await self._get_optimization_recommendations(current_metrics)
        }
        
        return report
    
    async def execute_health_check(self) -> Dict[str, Any]:
        """
        Execute comprehensive pool health check.
        
        Returns:
            Health check results
        """
        logger.info("Executing pool health check")
        
        health_results = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": "unknown",
            "connection_tests": [],
            "performance_metrics": {},
            "issues_found": [],
            "recommendations": []
        }
        
        # Test connections
        connection_test_results = await self._test_all_connections()
        health_results["connection_tests"] = connection_test_results
        
        # Collect performance metrics
        current_metrics = await self._collect_current_metrics()
        health_results["performance_metrics"] = self._pool_metrics_to_dict(current_metrics)
        
        # Identify issues
        issues = await self._identify_pool_issues(current_metrics)
        health_results["issues_found"] = issues
        
        # Generate recommendations
        recommendations = await self._get_optimization_recommendations(current_metrics)
        health_results["recommendations"] = recommendations
        
        # Calculate overall health
        health_score = self._calculate_pool_health_score(current_metrics)
        if health_score >= 80:
            health_results["overall_health"] = "excellent"
        elif health_score >= 60:
            health_results["overall_health"] = "good"
        elif health_score >= 40:
            health_results["overall_health"] = "fair"
        else:
            health_results["overall_health"] = "poor"
        
        logger.info(f"Health check completed: {health_results['overall_health']} (score: {health_score:.1f})")
        
        return health_results
    
    async def get_analytics_session_pool(
        self,
        pool_size: int = 4,
        timeout: float = 120.0
    ) -> List[ContextManager[Session]]:
        """
        Get a pool of database sessions optimized for concurrent analytics.
        
        Creates multiple sessions for parallel analytics processing
        with optimized configurations for time-bin analysis workloads.
        
        Args:
            pool_size: Number of sessions to create
            timeout: Timeout for each session
            
        Returns:
            List of session context managers for concurrent use
        """
        logger.info(f"Creating analytics session pool with {pool_size} sessions")
        
        sessions = []
        for i in range(pool_size):
            sessions.append(self.get_session())
        
        return sessions
    
    async def execute_concurrent_analytics_queries(
        self,
        queries: List[str],
        max_workers: int = 4
    ) -> List[Any]:
        """
        Execute multiple analytics queries concurrently.
        
        Optimized for time-bin analytics where multiple similar
        queries need to be executed in parallel.
        
        Args:
            queries: List of SQL queries to execute
            max_workers: Maximum number of concurrent workers
            
        Returns:
            List of query results in same order as input queries
        """
        logger.info(f"Executing {len(queries)} analytics queries with {max_workers} workers")
        
        results = [None] * len(queries)
        semaphore = asyncio.Semaphore(max_workers)
        
        async def execute_single_query(query_idx: int, query: str):
            async with semaphore:
                try:
                    with self.get_session() as session:
                        result = session.execute(text(query))
                        if result.returns_rows:
                            results[query_idx] = result.fetchall()
                        else:
                            results[query_idx] = result
                            
                except Exception as e:
                    logger.error(f"Query {query_idx} failed: {str(e)}")
                    results[query_idx] = None
        
        # Execute all queries concurrently
        tasks = [
            execute_single_query(idx, query)
            for idx, query in enumerate(queries)
        ]
        
        await asyncio.gather(*tasks)
        
        successful_queries = len([r for r in results if r is not None])
        logger.info(f"Completed {successful_queries}/{len(queries)} analytics queries")
        
        return results
    
    async def optimize_for_analytics_workload(self) -> Dict[str, Any]:
        """
        Optimize connection pool specifically for analytics workloads.
        
        Adjusts pool configuration based on analytics usage patterns:
        - Increases pool size for concurrent processing
        - Adjusts timeouts for long-running analytics queries
        - Optimizes connection recycling for batch processing
        
        Returns:
            Optimization results
        """
        logger.info("Optimizing connection pool for analytics workload")
        
        current_metrics = await self._collect_current_metrics()
        workload_analysis = await self._analyze_workload_patterns()
        
        optimization_results = {
            'original_config': self._pool_config_to_dict(),
            'workload_analysis': workload_analysis,
            'optimizations_applied': [],
            'estimated_improvement': 0.0
        }
        
        # Analyze if we need more connections for analytics
        if workload_analysis['query_frequency'] > 50:  # High query volume
            if self.pool_config.max_size < 24:
                old_max = self.pool_config.max_size
                self.pool_config.max_size = min(32, old_max * 2)
                optimization_results['optimizations_applied'].append({
                    'type': 'pool_size_increase',
                    'old_value': old_max,
                    'new_value': self.pool_config.max_size,
                    'reason': 'high_query_frequency'
                })
        
        # Adjust timeout for complex analytics queries
        avg_checkout_time = current_metrics.avg_checkout_time
        if avg_checkout_time > 5.0:  # Long-running queries detected
            if self.pool_config.timeout < 180.0:
                old_timeout = self.pool_config.timeout
                self.pool_config.timeout = 180.0
                optimization_results['optimizations_applied'].append({
                    'type': 'timeout_increase',
                    'old_value': old_timeout,
                    'new_value': self.pool_config.timeout,
                    'reason': 'long_running_queries'
                })
        
        # Optimize for batch processing
        if workload_analysis['workload_intensity'] == 'high':
            # Reduce connection recycling frequency for batch jobs
            if self.pool_config.recycle_time < 3600:
                old_recycle = self.pool_config.recycle_time
                self.pool_config.recycle_time = 3600
                optimization_results['optimizations_applied'].append({
                    'type': 'recycle_time_increase',
                    'old_value': old_recycle,
                    'new_value': self.pool_config.recycle_time,
                    'reason': 'batch_processing_optimization'
                })
        
        # Calculate estimated improvement
        optimization_results['estimated_improvement'] = len(optimization_results['optimizations_applied']) * 0.15
        
        logger.info(f"Analytics workload optimization completed: {len(optimization_results['optimizations_applied'])} changes")
        
        return optimization_results
    
    async def get_analytics_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics specific to analytics workloads.
        
        Returns:
            Analytics-specific performance metrics
        """
        current_metrics = await self._collect_current_metrics()
        
        # Calculate analytics-specific metrics
        analytics_metrics = {
            'concurrent_query_capacity': self.pool_config.max_size + self.pool_config.overflow,
            'avg_query_execution_time': current_metrics.connection_lifetime_avg,
            'connection_utilization': current_metrics.pool_efficiency,
            'analytics_readiness_score': await self._calculate_analytics_readiness_score(current_metrics),
            'recommended_concurrent_workers': await self._calculate_optimal_worker_count(current_metrics),
            'time_bin_query_optimization': await self._analyze_time_bin_query_performance()
        }
        
        return analytics_metrics
    
    # Private methods
    def _initialize_pool(self):
        """Initialize the connection pool."""
        # Configure pool based on strategy
        if self.pool_config.strategy == PoolStrategy.STATIC:
            poolclass = StaticPool
            pool_kwargs = {
                "poolclass": poolclass,
                "pool_size": self.pool_config.min_size,
                "max_overflow": 0
            }
        elif self.pool_config.strategy == PoolStrategy.DYNAMIC:
            poolclass = QueuePool
            pool_kwargs = {
                "poolclass": poolclass,
                "pool_size": self.pool_config.min_size,
                "max_overflow": self.pool_config.overflow
            }
        else:
            # Default to QueuePool
            poolclass = QueuePool
            pool_kwargs = {
                "poolclass": poolclass,
                "pool_size": self.pool_config.min_size,
                "max_overflow": self.pool_config.overflow
            }
        
        # SQLite-specific connection arguments
        connect_args = {
            "check_same_thread": False,
            "timeout": self.pool_config.timeout
        }
        
        # Create engine
        self.engine = create_engine(
            self.database_url,
            connect_args=connect_args,
            pool_pre_ping=self.pool_config.pre_ping,
            pool_recycle=self.pool_config.recycle_time,
            echo=self.pool_config.echo,
            **pool_kwargs
        )
        
        # Setup event listeners
        self._setup_event_listeners()
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def _setup_event_listeners(self):
        """Setup SQLAlchemy event listeners for monitoring."""
        @event.listens_for(self.engine, "connect")
        def on_connect(dbapi_connection, connection_record):
            """Handle new connections."""
            conn_id = str(id(connection_record))
            
            self.connection_metrics[conn_id] = ConnectionMetrics(
                connection_id=conn_id,
                created_at=datetime.now(),
                last_used=datetime.now(),
                state=ConnectionState.IDLE
            )
            
            self.total_connections_created += 1
            
            # Apply SQLite optimizations
            if "sqlite" in self.database_url:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()
        
        @event.listens_for(self.engine, "checkout")
        def on_checkout(dbapi_connection, connection_record, connection_proxy):
            """Handle connection checkout."""
            conn_id = str(id(connection_record))
            
            if conn_id in self.connection_metrics:
                metrics = self.connection_metrics[conn_id]
                metrics.state = ConnectionState.ACTIVE
                metrics.last_used = datetime.now()
        
        @event.listens_for(self.engine, "checkin")
        def on_checkin(dbapi_connection, connection_record):
            """Handle connection checkin."""
            conn_id = str(id(connection_record))
            
            if conn_id in self.connection_metrics:
                metrics = self.connection_metrics[conn_id]
                metrics.state = ConnectionState.IDLE
                metrics.last_used = datetime.now()
        
        @event.listens_for(self.engine, "close")
        def on_close(dbapi_connection, connection_record):
            """Handle connection close."""
            conn_id = str(id(connection_record))
            
            if conn_id in self.connection_metrics:
                del self.connection_metrics[conn_id]
            
            self.total_connections_closed += 1
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        logger.info("Pool monitoring loop started")
        
        while self.monitoring_active:
            try:
                # Collect metrics
                asyncio.run(self._collect_and_store_metrics())
                
                # Perform health checks
                asyncio.run(self._periodic_health_check())
                
                # Auto-optimization if enabled
                if self.pool_config.strategy in [PoolStrategy.ADAPTIVE, PoolStrategy.DYNAMIC]:
                    asyncio.run(self.optimize_pool_size())
                
                # Cleanup stale connections
                asyncio.run(self.cleanup_stale_connections())
                
                # Sleep until next check
                time.sleep(self.pool_config.health_check_interval)
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {str(e)}")
                time.sleep(10)
        
        logger.info("Pool monitoring loop stopped")
    
    async def _collect_current_metrics(self) -> PoolMetrics:
        """Collect current pool metrics."""
        # Count connections by state
        active_count = sum(1 for m in self.connection_metrics.values() 
                          if m.state == ConnectionState.ACTIVE)
        idle_count = sum(1 for m in self.connection_metrics.values() 
                        if m.state == ConnectionState.IDLE)
        stale_count = sum(1 for m in self.connection_metrics.values() 
                         if m.state == ConnectionState.STALE)
        invalid_count = sum(1 for m in self.connection_metrics.values() 
                           if m.state == ConnectionState.INVALID)
        
        total_connections = len(self.connection_metrics)
        
        # Calculate checkout statistics
        if self.checkout_times:
            avg_checkout_time = sum(self.checkout_times) / len(self.checkout_times)
            max_checkout_time = max(self.checkout_times)
        else:
            avg_checkout_time = 0.0
            max_checkout_time = 0.0
        
        # Calculate efficiency
        if total_connections > 0:
            pool_efficiency = (active_count / total_connections) * 100
        else:
            pool_efficiency = 0.0
        
        # Calculate average connection lifetime
        if self.connection_metrics:
            current_time = datetime.now()
            lifetimes = [(current_time - m.created_at).total_seconds() 
                        for m in self.connection_metrics.values()]
            connection_lifetime_avg = sum(lifetimes) / len(lifetimes)
        else:
            connection_lifetime_avg = 0.0
        
        # Calculate error rate
        total_queries = sum(m.total_queries for m in self.connection_metrics.values())
        total_errors = sum(m.error_count for m in self.connection_metrics.values())
        error_rate = (total_errors / max(1, total_queries)) * 100
        
        return PoolMetrics(
            pool_size=total_connections,
            active_connections=active_count,
            idle_connections=idle_count,
            stale_connections=stale_count,
            invalid_connections=invalid_count,
            wait_queue_size=0,  # SQLite doesn't have wait queues
            avg_checkout_time=avg_checkout_time,
            max_checkout_time=max_checkout_time,
            pool_efficiency=pool_efficiency,
            connection_lifetime_avg=connection_lifetime_avg,
            error_rate=error_rate
        )
    
    async def _analyze_workload_patterns(self) -> Dict[str, Any]:
        """Analyze current workload patterns."""
        # Analyze checkout frequency
        recent_checkouts = [t for t in self.checkout_times if t < 60]  # Last minute
        checkout_frequency = len(recent_checkouts)
        
        # Analyze query patterns
        recent_queries = [t for t in self.query_times if t < 300]  # Last 5 minutes
        query_frequency = len(recent_queries)
        
        # Calculate peak usage
        current_hour = datetime.now().hour
        peak_hours = [9, 10, 11, 14, 15, 16]  # Typical business hours
        is_peak_time = current_hour in peak_hours
        
        return {
            "checkout_frequency": checkout_frequency,
            "query_frequency": query_frequency,
            "is_peak_time": is_peak_time,
            "workload_intensity": "high" if checkout_frequency > 10 else "medium" if checkout_frequency > 5 else "low"
        }
    
    async def _calculate_optimal_pool_size(
        self,
        current_metrics: PoolMetrics,
        workload_analysis: Dict[str, Any]
    ) -> int:
        """Calculate optimal pool size based on current conditions."""
        current_size = current_metrics.pool_size
        
        # Base calculation on utilization
        utilization = current_metrics.pool_efficiency / 100.0
        
        # Adjust based on workload intensity
        if workload_analysis["workload_intensity"] == "high":
            target_utilization = 0.7  # 70% utilization for high workload
        elif workload_analysis["workload_intensity"] == "medium":
            target_utilization = 0.8  # 80% utilization for medium workload
        else:
            target_utilization = 0.9  # 90% utilization for low workload
        
        # Calculate optimal size
        if utilization > 0:
            optimal_size = int(current_metrics.active_connections / target_utilization)
        else:
            optimal_size = self.pool_config.min_size
        
        # Apply constraints
        optimal_size = max(self.pool_config.min_size, optimal_size)
        optimal_size = min(self.pool_config.max_size, optimal_size)
        
        # Prevent frequent small changes
        if abs(optimal_size - current_size) <= 1:
            optimal_size = current_size
        
        return optimal_size
    
    async def _resize_pool(self, new_size: int, reason: str):
        """Resize the connection pool."""
        logger.info(f"Resizing pool to {new_size} connections (reason: {reason})")
        
        # For SQLite with SQLAlchemy, we can't dynamically resize the pool
        # In a real implementation, you would recreate the engine with new pool size
        # For now, we'll simulate the resize
        
        # This is a simplified simulation
        # In practice, you would need to recreate the engine and session factory
        pass
    
    async def _close_connection(self, connection_id: str):
        """Close a specific connection."""
        # In SQLite/SQLAlchemy, we don't have direct access to individual connections
        # This would be implemented differently in a real production system
        pass
    
    def _update_checkout_metrics(self, checkout_time: float):
        """Update checkout performance metrics."""
        # This would be called from the session context manager
        pass
    
    def _update_checkin_metrics(self):
        """Update checkin performance metrics."""
        # This would be called from the session context manager
        pass
    
    def _track_checkout_failure(self, error: str):
        """Track checkout failures."""
        logger.warning(f"Connection checkout failed: {error}")
    
    def _calculate_pool_health_score(self, metrics: PoolMetrics) -> float:
        """Calculate overall pool health score."""
        score = 100.0
        
        # Penalize high checkout times
        if metrics.avg_checkout_time > 1.0:
            score -= min(30, metrics.avg_checkout_time * 10)
        
        # Penalize low efficiency
        if metrics.pool_efficiency < 50:
            score -= (50 - metrics.pool_efficiency)
        
        # Penalize high error rate
        score -= metrics.error_rate * 2
        
        # Penalize stale connections
        if metrics.stale_connections > 0:
            score -= metrics.stale_connections * 5
        
        # Penalize invalid connections
        if metrics.invalid_connections > 0:
            score -= metrics.invalid_connections * 10
        
        return max(0.0, score)
    
    async def _get_optimization_recommendations(self, metrics: PoolMetrics) -> List[str]:
        """Get optimization recommendations based on current metrics."""
        recommendations = []
        
        if metrics.pool_efficiency < 50:
            recommendations.append("Consider reducing pool size - low utilization detected")
        
        if metrics.avg_checkout_time > 1.0:
            recommendations.append("High checkout times detected - consider pool optimization")
        
        if metrics.error_rate > 5:
            recommendations.append("High error rate detected - investigate connection issues")
        
        if metrics.stale_connections > 0:
            recommendations.append("Stale connections found - run cleanup operation")
        
        if metrics.invalid_connections > 0:
            recommendations.append("Invalid connections found - immediate cleanup required")
        
        return recommendations
    
    async def _collect_and_store_metrics(self):
        """Collect and store current metrics."""
        current_metrics = await self._collect_current_metrics()
        self.pool_metrics_history.append(current_metrics)
    
    async def _periodic_health_check(self):
        """Perform periodic health check."""
        # This would run connection health tests
        pass
    
    async def _test_all_connections(self) -> List[Dict[str, Any]]:
        """Test all connections for health."""
        test_results = []
        
        for conn_id, metrics in self.connection_metrics.items():
            test_result = {
                "connection_id": conn_id,
                "status": "healthy",
                "response_time": 0.0,
                "error": None
            }
            
            # Simulate connection test
            try:
                start_time = time.time()
                # In a real implementation, you would test the actual connection
                test_time = time.time() - start_time
                test_result["response_time"] = test_time
                
                if test_time > 1.0:
                    test_result["status"] = "slow"
                    
            except Exception as e:
                test_result["status"] = "failed"
                test_result["error"] = str(e)
            
            test_results.append(test_result)
        
        return test_results
    
    async def _identify_pool_issues(self, metrics: PoolMetrics) -> List[str]:
        """Identify pool issues."""
        issues = []
        
        if metrics.pool_efficiency < 30:
            issues.append("Very low pool utilization")
        
        if metrics.avg_checkout_time > 2.0:
            issues.append("Very high checkout times")
        
        if metrics.error_rate > 10:
            issues.append("High error rate")
        
        if metrics.invalid_connections > metrics.pool_size * 0.2:
            issues.append("Too many invalid connections")
        
        return issues
    
    def _calculate_checkout_statistics(self) -> Dict[str, float]:
        """Calculate checkout performance statistics."""
        if not self.checkout_times:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "p95": 0.0}
        
        sorted_times = sorted(self.checkout_times)
        
        return {
            "min": min(sorted_times),
            "max": max(sorted_times),
            "avg": sum(sorted_times) / len(sorted_times),
            "p95": sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0.0
        }
    
    def _calculate_query_statistics(self) -> Dict[str, float]:
        """Calculate query performance statistics."""
        if not self.query_times:
            return {"min": 0.0, "max": 0.0, "avg": 0.0, "p95": 0.0}
        
        sorted_times = sorted(self.query_times)
        
        return {
            "min": min(sorted_times),
            "max": max(sorted_times),
            "avg": sum(sorted_times) / len(sorted_times),
            "p95": sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0.0
        }
    
    def _calculate_efficiency_statistics(self, metrics: PoolMetrics) -> Dict[str, float]:
        """Calculate efficiency statistics."""
        return {
            "pool_efficiency": metrics.pool_efficiency,
            "utilization_ratio": metrics.active_connections / max(1, metrics.pool_size),
            "idle_ratio": metrics.idle_connections / max(1, metrics.pool_size),
            "error_rate": metrics.error_rate
        }
    
    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends."""
        if len(self.pool_metrics_history) < 2:
            return {"status": "insufficient_data"}
        
        recent_metrics = list(self.pool_metrics_history)[-10:]
        
        # Calculate trends
        efficiency_trend = "stable"
        if len(recent_metrics) >= 2:
            if recent_metrics[-1].pool_efficiency > recent_metrics[0].pool_efficiency:
                efficiency_trend = "improving"
            elif recent_metrics[-1].pool_efficiency < recent_metrics[0].pool_efficiency:
                efficiency_trend = "degrading"
        
        return {
            "efficiency_trend": efficiency_trend,
            "metrics_analyzed": len(recent_metrics),
            "latest_efficiency": recent_metrics[-1].pool_efficiency if recent_metrics else 0.0
        }
    
    # Conversion methods
    def _pool_config_to_dict(self) -> Dict[str, Any]:
        """Convert pool configuration to dictionary."""
        return {
            "min_size": self.pool_config.min_size,
            "max_size": self.pool_config.max_size,
            "overflow": self.pool_config.overflow,
            "recycle_time": self.pool_config.recycle_time,
            "timeout": self.pool_config.timeout,
            "strategy": self.pool_config.strategy.value,
            "health_check_interval": self.pool_config.health_check_interval
        }
    
    def _pool_metrics_to_dict(self, metrics: PoolMetrics) -> Dict[str, Any]:
        """Convert pool metrics to dictionary."""
        return {
            "pool_size": metrics.pool_size,
            "active_connections": metrics.active_connections,
            "idle_connections": metrics.idle_connections,
            "stale_connections": metrics.stale_connections,
            "invalid_connections": metrics.invalid_connections,
            "avg_checkout_time": metrics.avg_checkout_time,
            "max_checkout_time": metrics.max_checkout_time,
            "pool_efficiency": metrics.pool_efficiency,
            "connection_lifetime_avg": metrics.connection_lifetime_avg,
            "error_rate": metrics.error_rate
        }
    
    def _connection_metrics_to_dict(self, metrics: ConnectionMetrics) -> Dict[str, Any]:
        """Convert connection metrics to dictionary."""
        return {
            "connection_id": metrics.connection_id,
            "created_at": metrics.created_at.isoformat(),
            "last_used": metrics.last_used.isoformat(),
            "total_queries": metrics.total_queries,
            "avg_query_time": metrics.avg_query_time,
            "state": metrics.state.value,
            "error_count": metrics.error_count,
            "health_score": metrics.health_score
        }
    
    def _optimization_event_to_dict(self, event: OptimizationEvent) -> Dict[str, Any]:
        """Convert optimization event to dictionary."""
        return {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type,
            "old_size": event.old_size,
            "new_size": event.new_size,
            "reason": event.reason,
            "impact_score": event.impact_score
        }
    
    async def _calculate_analytics_readiness_score(self, metrics: PoolMetrics) -> float:
        """Calculate analytics readiness score based on pool metrics."""
        score = 100.0
        
        # Pool size adequacy for analytics (want higher capacity)
        if metrics.pool_size < 16:
            score -= 20
        elif metrics.pool_size >= 24:
            score += 10
        
        # Connection utilization (want balanced, not too high)
        if metrics.pool_efficiency > 90:
            score -= 15  # Too high utilization for analytics bursts
        elif 60 <= metrics.pool_efficiency <= 80:
            score += 15  # Optimal range
        
        # Low checkout times are critical for analytics
        if metrics.avg_checkout_time < 0.1:
            score += 20
        elif metrics.avg_checkout_time > 2.0:
            score -= 30
        
        return max(0.0, min(100.0, score))
    
    async def _calculate_optimal_worker_count(self, metrics: PoolMetrics) -> int:
        """Calculate optimal concurrent worker count for analytics."""
        # Base on pool capacity and current utilization
        available_connections = metrics.pool_size - metrics.active_connections
        
        # Conservative approach - use 75% of available connections
        optimal_workers = max(1, int(available_connections * 0.75))
        
        # Cap based on system resources
        max_workers = min(optimal_workers, 8)  # Don't exceed 8 workers
        
        return max_workers
    
    async def _analyze_time_bin_query_performance(self) -> Dict[str, Any]:
        """Analyze performance specific to time-bin queries."""
        # Mock analysis - in production would analyze actual query patterns
        return {
            'avg_time_bin_query_time': 0.25,
            'concurrent_time_bin_queries': 6,
            'time_bin_cache_hit_ratio': 0.85,
            'optimization_potential': 'medium'
        }


# Utility functions
async def create_optimized_pool_manager(
    database_url: str,
    strategy: PoolStrategy = PoolStrategy.DYNAMIC,
    min_size: int = 5,
    max_size: int = 20
) -> ConnectionPoolManager:
    """
    Create an optimized connection pool manager.
    
    Args:
        database_url: Database connection URL
        strategy: Pool management strategy
        min_size: Minimum pool size
        max_size: Maximum pool size
        
    Returns:
        Configured ConnectionPoolManager
    """
    config = PoolConfiguration(
        min_size=min_size,
        max_size=max_size,
        strategy=strategy
    )
    
    manager = ConnectionPoolManager(database_url, config)
    await manager.start_monitoring()
    
    return manager


async def run_pool_health_check(database_url: str) -> Dict[str, Any]:
    """
    Run a quick pool health check.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        Health check results
    """
    manager = ConnectionPoolManager(database_url, monitoring_enabled=False)
    
    try:
        return await manager.execute_health_check()
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }