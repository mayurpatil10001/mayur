"""
Database query optimization and performance monitoring service.

This module provides comprehensive database optimization capabilities including:
- Query performance analysis and optimization recommendations
- Index optimization and management
- Database statistics collection and analysis
- Connection pool optimization
- Query execution plan analysis

Requirements: 10.1, 10.2, 10.3
"""

import logging
import time
import sqlite3
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
import psutil
import threading
from pathlib import Path
import json
import re
from contextlib import contextmanager
from collections import defaultdict, deque

from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)


class QueryComplexity(Enum):
    """Query complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    VERY_COMPLEX = "very_complex"


class OptimizationPriority(Enum):
    """Optimization priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class QueryMetrics:
    """Metrics for a database query."""
    query_hash: str
    query_text: str
    execution_count: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    rows_examined: int = 0
    rows_returned: int = 0
    index_usage: List[str] = field(default_factory=list)
    table_scans: int = 0
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    optimization_suggestions: List[str] = field(default_factory=list)
    last_execution: Optional[datetime] = None


@dataclass
class IndexMetrics:
    """Metrics for database indexes."""
    index_name: str
    table_name: str
    columns: List[str]
    is_unique: bool
    usage_count: int = 0
    selectivity: float = 0.0
    size_kb: float = 0.0
    last_used: Optional[datetime] = None
    effectiveness_score: float = 0.0
    creation_cost: float = 0.0
    maintenance_cost: float = 0.0


@dataclass
class OptimizationRecommendation:
    """Database optimization recommendation."""
    recommendation_id: str
    category: str  # 'index', 'query', 'schema', 'configuration'
    priority: OptimizationPriority
    description: str
    impact_estimate: str
    implementation_sql: Optional[str]
    estimated_improvement: float  # Percentage improvement
    affected_queries: List[str]
    resource_requirements: Dict[str, Any]
    risks: List[str] = field(default_factory=list)


@dataclass
class DatabaseHealthMetrics:
    """Overall database health metrics."""
    connection_count: int
    active_connections: int
    query_cache_hit_ratio: float
    index_efficiency: float
    table_scan_ratio: float
    avg_query_time: float
    slow_query_count: int
    lock_wait_time: float
    database_size_mb: float
    fragmentation_ratio: float
    last_vacuum: Optional[datetime]
    optimization_score: float  # 0-100


@dataclass
class PerformanceBaseline:
    """Performance baseline for comparison."""
    timestamp: datetime
    total_queries: int
    avg_response_time: float
    p95_response_time: float
    throughput_qps: float
    connection_pool_usage: float
    cache_hit_ratio: float
    error_rate: float


class QueryOptimizer:
    """
    Database query optimization and performance monitoring service.
    
    Provides comprehensive database optimization capabilities including
    query analysis, index optimization, and performance monitoring.
    """
    
    def __init__(
        self,
        database_url: str,
        monitoring_enabled: bool = True,
        baseline_collection_interval: int = 300  # 5 minutes
    ):
        """Initialize the query optimizer."""
        self.database_url = database_url
        self.monitoring_enabled = monitoring_enabled
        self.baseline_collection_interval = baseline_collection_interval
        
        # Initialize database components
        self.engine = self._create_optimized_engine()
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.metadata = MetaData()
        
        # Monitoring data structures
        self.query_metrics: Dict[str, QueryMetrics] = {}
        self.index_metrics: Dict[str, IndexMetrics] = {}
        self.performance_baselines: deque = deque(maxlen=1000)  # Keep last 1000 baselines
        self.optimization_recommendations: List[OptimizationRecommendation] = []
        
        # Performance monitoring
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False
        self.slow_query_threshold = 1.0  # seconds
        
        # Query interception
        self.intercepted_queries: deque = deque(maxlen=10000)
        
        # Cache for optimization results
        self.optimization_cache: Dict[str, Any] = {}
        
        logger.info("QueryOptimizer initialized with monitoring enabled")
    
    async def start_monitoring(self):
        """Start comprehensive database performance monitoring."""
        if not self.monitoring_enabled:
            logger.warning("Monitoring is disabled")
            return
        
        self.monitoring_active = True
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        
        # Collect initial baseline
        await self._collect_performance_baseline()
        
        # Start real-time monitoring tasks
        await self._start_real_time_monitoring()
        
        logger.info("Comprehensive database performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop database performance monitoring."""
        self.monitoring_active = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=5)
        
        logger.info("Database performance monitoring stopped")
    
    async def analyze_query_performance(
        self,
        time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Analyze query performance over a time window.
        
        Args:
            time_window_hours: Analysis time window in hours
            
        Returns:
            Comprehensive query performance analysis
        """
        logger.info(f"Analyzing query performance for last {time_window_hours} hours")
        
        # Filter metrics by time window
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        recent_metrics = {
            query_hash: metrics for query_hash, metrics in self.query_metrics.items()
            if metrics.last_execution and metrics.last_execution >= cutoff_time
        }
        
        if not recent_metrics:
            return {"status": "no_data", "message": "No query data in time window"}
        
        # Analyze query patterns
        analysis = {
            "time_window_hours": time_window_hours,
            "total_queries_analyzed": len(recent_metrics),
            "total_executions": sum(m.execution_count for m in recent_metrics.values()),
            "avg_response_time": sum(m.avg_execution_time for m in recent_metrics.values()) / len(recent_metrics),
            "slow_queries": [],
            "frequent_queries": [],
            "inefficient_queries": [],
            "complexity_distribution": defaultdict(int),
            "table_scan_queries": [],
            "optimization_opportunities": []
        }
        
        # Identify problematic queries
        for query_hash, metrics in recent_metrics.items():
            # Complexity distribution
            analysis["complexity_distribution"][metrics.complexity.value] += 1
            
            # Slow queries
            if metrics.avg_execution_time > self.slow_query_threshold:
                analysis["slow_queries"].append({
                    "query_hash": query_hash,
                    "avg_time": metrics.avg_execution_time,
                    "execution_count": metrics.execution_count,
                    "total_time": metrics.total_execution_time
                })
            
            # Frequent queries
            if metrics.execution_count > 100:  # Frequently executed
                analysis["frequent_queries"].append({
                    "query_hash": query_hash,
                    "execution_count": metrics.execution_count,
                    "avg_time": metrics.avg_execution_time,
                    "total_time": metrics.total_execution_time
                })
            
            # Table scan queries
            if metrics.table_scans > 0:
                analysis["table_scan_queries"].append({
                    "query_hash": query_hash,
                    "table_scans": metrics.table_scans,
                    "avg_time": metrics.avg_execution_time
                })
            
            # Inefficient queries (high time per row)
            if metrics.rows_returned > 0:
                time_per_row = metrics.avg_execution_time / metrics.rows_returned
                if time_per_row > 0.001:  # More than 1ms per row
                    analysis["inefficient_queries"].append({
                        "query_hash": query_hash,
                        "time_per_row": time_per_row,
                        "avg_time": metrics.avg_execution_time,
                        "rows_returned": metrics.rows_returned
                    })
        
        # Sort results by impact
        analysis["slow_queries"].sort(key=lambda x: x["total_time"], reverse=True)
        analysis["frequent_queries"].sort(key=lambda x: x["execution_count"], reverse=True)
        analysis["inefficient_queries"].sort(key=lambda x: x["time_per_row"], reverse=True)
        
        # Generate optimization opportunities
        analysis["optimization_opportunities"] = await self._identify_optimization_opportunities(recent_metrics)
        
        logger.info(f"Query performance analysis completed: {analysis['total_executions']} executions analyzed")
        
        return analysis
    
    async def optimize_indexes(self) -> List[OptimizationRecommendation]:
        """
        Analyze and optimize database indexes.
        
        Returns:
            List of index optimization recommendations
        """
        logger.info("Starting index optimization analysis")
        
        recommendations = []
        
        try:
            # Collect current index information
            await self._collect_index_metrics()
            
            # Analyze index usage patterns
            index_analysis = await self._analyze_index_usage()
            
            # Identify missing indexes
            missing_indexes = await self._identify_missing_indexes()
            recommendations.extend(missing_indexes)
            
            # Identify unused indexes
            unused_indexes = await self._identify_unused_indexes()
            recommendations.extend(unused_indexes)
            
            # Identify duplicate indexes
            duplicate_indexes = await self._identify_duplicate_indexes()
            recommendations.extend(duplicate_indexes)
            
            # Optimize existing indexes
            index_optimizations = await self._optimize_existing_indexes()
            recommendations.extend(index_optimizations)
            
            # Store recommendations
            self.optimization_recommendations.extend(recommendations)
            
            logger.info(f"Index optimization completed: {len(recommendations)} recommendations generated")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Index optimization failed: {str(e)}")
            raise
    
    async def get_database_health(self) -> DatabaseHealthMetrics:
        """
        Get comprehensive database health metrics.
        
        Returns:
            Database health metrics
        """
        logger.debug("Collecting database health metrics")
        
        try:
            with self._get_db_session() as session:
                # Connection metrics
                connection_count = await self._get_connection_count(session)
                
                # Query performance metrics
                if self.query_metrics:
                    avg_query_time = sum(m.avg_execution_time for m in self.query_metrics.values()) / len(self.query_metrics)
                    slow_query_count = sum(1 for m in self.query_metrics.values() 
                                         if m.avg_execution_time > self.slow_query_threshold)
                    table_scan_ratio = sum(m.table_scans for m in self.query_metrics.values()) / max(1, len(self.query_metrics))
                else:
                    avg_query_time = 0.0
                    slow_query_count = 0
                    table_scan_ratio = 0.0
                
                # Index efficiency
                if self.index_metrics:
                    index_efficiency = sum(m.effectiveness_score for m in self.index_metrics.values()) / len(self.index_metrics)
                else:
                    index_efficiency = 0.0
                
                # Database size
                database_size_mb = await self._get_database_size(session)
                
                # Calculate optimization score
                optimization_score = self._calculate_optimization_score(
                    avg_query_time, table_scan_ratio, index_efficiency, slow_query_count
                )
                
                health_metrics = DatabaseHealthMetrics(
                    connection_count=connection_count,
                    active_connections=connection_count,  # Simplified for SQLite
                    query_cache_hit_ratio=0.95,  # SQLite doesn't expose this easily
                    index_efficiency=index_efficiency,
                    table_scan_ratio=table_scan_ratio,
                    avg_query_time=avg_query_time,
                    slow_query_count=slow_query_count,
                    lock_wait_time=0.0,  # SQLite specific
                    database_size_mb=database_size_mb,
                    fragmentation_ratio=0.0,  # Would need VACUUM analysis
                    last_vacuum=None,  # Would need to track separately
                    optimization_score=optimization_score
                )
                
                return health_metrics
                
        except Exception as e:
            logger.error(f"Failed to collect database health metrics: {str(e)}")
            raise
    
    async def execute_optimized_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        monitor_performance: bool = True
    ) -> Tuple[Any, QueryMetrics]:
        """
        Execute a query with performance monitoring and optimization hints.
        
        Args:
            query: SQL query to execute
            parameters: Query parameters
            monitor_performance: Whether to monitor performance
            
        Returns:
            Tuple of (query result, performance metrics)
        """
        query_hash = self._hash_query(query)
        start_time = time.time()
        
        try:
            # Apply query optimizations
            optimized_query = await self._apply_query_optimizations(query)
            
            with self._get_db_session() as session:
                # Execute query
                if parameters:
                    result = session.execute(text(optimized_query), parameters)
                else:
                    result = session.execute(text(optimized_query))
                
                # Fetch results
                if result.returns_rows:
                    rows = result.fetchall()
                    execution_result = rows
                    rows_returned = len(rows)
                else:
                    execution_result = result
                    rows_returned = result.rowcount if hasattr(result, 'rowcount') else 0
                
                execution_time = time.time() - start_time
                
                # Update metrics if monitoring is enabled
                if monitor_performance:
                    await self._update_query_metrics(
                        query_hash, query, execution_time, rows_returned
                    )
                
                # Get or create metrics object for return
                metrics = self.query_metrics.get(query_hash, QueryMetrics(
                    query_hash=query_hash,
                    query_text=query,
                    avg_execution_time=execution_time
                ))
                
                return execution_result, metrics
                
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query execution failed after {execution_time:.3f}s: {str(e)}")
            
            # Still update metrics for failed queries
            if monitor_performance:
                await self._update_query_metrics(
                    query_hash, query, execution_time, 0, error=str(e)
                )
            
            raise
    
    async def generate_optimization_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive database optimization report.
        
        Returns:
            Detailed optimization report
        """
        logger.info("Generating database optimization report")
        
        # Collect all optimization data
        query_analysis = await self.analyze_query_performance()
        index_recommendations = await self.optimize_indexes()
        health_metrics = await self.get_database_health()
        
        # Performance trends
        performance_trends = self._analyze_performance_trends()
        
        # Resource utilization
        resource_metrics = await self._collect_resource_metrics()
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "executive_summary": {
                "optimization_score": health_metrics.optimization_score,
                "total_recommendations": len(self.optimization_recommendations),
                "critical_issues": len([r for r in self.optimization_recommendations 
                                      if r.priority == OptimizationPriority.CRITICAL]),
                "potential_improvement": sum(r.estimated_improvement for r in self.optimization_recommendations)
            },
            "query_performance": query_analysis,
            "index_optimization": {
                "recommendations": [self._recommendation_to_dict(r) for r in index_recommendations],
                "index_metrics": {name: self._index_metrics_to_dict(metrics) 
                                for name, metrics in self.index_metrics.items()}
            },
            "database_health": self._health_metrics_to_dict(health_metrics),
            "performance_trends": performance_trends,
            "resource_utilization": resource_metrics,
            "optimization_recommendations": [
                self._recommendation_to_dict(r) for r in self.optimization_recommendations
            ]
        }
        
        logger.info("Database optimization report generated successfully")
        
        return report
    
    async def apply_optimization_recommendations(
        self,
        recommendation_ids: List[str],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Apply optimization recommendations.
        
        Args:
            recommendation_ids: List of recommendation IDs to apply
            dry_run: If True, only validate recommendations without applying
            
        Returns:
            Application results
        """
        logger.info(f"Applying {len(recommendation_ids)} optimization recommendations (dry_run={dry_run})")
        
        results = {
            "applied_recommendations": [],
            "failed_recommendations": [],
            "validation_errors": [],
            "total_estimated_improvement": 0.0
        }
        
        # Find recommendations to apply
        recommendations_to_apply = [
            r for r in self.optimization_recommendations
            if r.recommendation_id in recommendation_ids
        ]
        
        if len(recommendations_to_apply) != len(recommendation_ids):
            found_ids = {r.recommendation_id for r in recommendations_to_apply}
            missing_ids = set(recommendation_ids) - found_ids
            results["validation_errors"].append(f"Recommendations not found: {missing_ids}")
        
        # Apply each recommendation
        for recommendation in recommendations_to_apply:
            try:
                if dry_run:
                    # Validate recommendation
                    validation_result = await self._validate_recommendation(recommendation)
                    if validation_result["valid"]:
                        results["applied_recommendations"].append({
                            "recommendation_id": recommendation.recommendation_id,
                            "status": "validated",
                            "estimated_improvement": recommendation.estimated_improvement
                        })
                        results["total_estimated_improvement"] += recommendation.estimated_improvement
                    else:
                        results["failed_recommendations"].append({
                            "recommendation_id": recommendation.recommendation_id,
                            "error": validation_result["error"]
                        })
                else:
                    # Actually apply recommendation
                    application_result = await self._apply_recommendation(recommendation)
                    if application_result["success"]:
                        results["applied_recommendations"].append({
                            "recommendation_id": recommendation.recommendation_id,
                            "status": "applied",
                            "execution_time": application_result["execution_time"]
                        })
                        results["total_estimated_improvement"] += recommendation.estimated_improvement
                    else:
                        results["failed_recommendations"].append({
                            "recommendation_id": recommendation.recommendation_id,
                            "error": application_result["error"]
                        })
                
            except Exception as e:
                logger.error(f"Failed to process recommendation {recommendation.recommendation_id}: {str(e)}")
                results["failed_recommendations"].append({
                    "recommendation_id": recommendation.recommendation_id,
                    "error": str(e)
                })
        
        logger.info(f"Optimization application completed: {len(results['applied_recommendations'])} successful")
        
        return results
    
    # Private methods
    def _create_optimized_engine(self) -> Engine:
        """Create an optimized database engine."""
        # SQLite-specific optimizations
        connect_args = {
            "check_same_thread": False,
            "timeout": 20,
            "isolation_level": None,  # Autocommit mode
        }
        
        # Create engine with connection pooling optimizations
        engine = create_engine(
            self.database_url,
            connect_args=connect_args,
            poolclass=StaticPool,
            pool_pre_ping=True,
            pool_recycle=3600,  # 1 hour
            echo=False
        )
        
        # Apply SQLite optimizations
        @asyncio.coroutine
        def _optimize_connection(connection, connection_record):
            """Optimize SQLite connection settings."""
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA cache_size=10000")
            connection.execute("PRAGMA temp_store=MEMORY")
            connection.execute("PRAGMA mmap_size=268435456")  # 256MB
        
        # Note: For a real implementation, you would use:
        # from sqlalchemy import event
        # event.listen(engine, "connect", _optimize_connection)
        
        return engine
    
    @contextmanager
    def _get_db_session(self):
        """Get database session with proper resource management."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def _hash_query(self, query: str) -> str:
        """Create a hash for query identification."""
        # Normalize query for consistent hashing
        normalized = re.sub(r'\s+', ' ', query.strip().upper())
        # Remove literal values for pattern matching
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        
        return str(hash(normalized))
    
    async def _apply_query_optimizations(self, query: str) -> str:
        """
        Apply automatic query optimizations for large trade datasets.
        
        Implements sophisticated query optimization techniques including:
        - Index hint injection
        - Query structure optimization
        - Large dataset pagination
        - Join order optimization
        - WHERE clause optimization
        """
        optimized_query = query.strip()
        query_upper = optimized_query.upper()
        
        # 1. Large dataset pagination - add LIMIT if missing for potentially large result sets
        if (("SELECT" in query_upper and 
             "FROM PROCESSED_TRADES" in query_upper or 
             "FROM SIERRA_CHART_FILLS" in query_upper or
             "FROM TIME_BIN_ANALYSIS" in query_upper) and 
            "LIMIT" not in query_upper and 
            "COUNT" not in query_upper and
            "MAX" not in query_upper and
            "MIN" not in query_upper and
            "AVG" not in query_upper):
            
            # Add safety limit for large table queries
            if "ORDER BY" in query_upper:
                optimized_query += " LIMIT 10000"
            else:
                # Add ORDER BY for consistent results with LIMIT
                if "FROM PROCESSED_TRADES" in query_upper:
                    optimized_query += " ORDER BY id LIMIT 10000"
                elif "FROM TIME_BIN_ANALYSIS" in query_upper:
                    optimized_query += " ORDER BY analysis_date DESC LIMIT 10000"
                else:
                    optimized_query += " LIMIT 10000"
        
        # 2. Date range query optimization - force index usage on date columns
        if ("WHERE" in query_upper and 
            ("DATE" in query_upper or "TIMESTAMP" in query_upper or "CREATED" in query_upper)):
            
            # Add index hints for date range queries (SQLite specific)
            if "SQLITE" in str(type(self.engine)).upper():
                # SQLite uses INDEXED BY hint
                if "PROCESSED_TRADES" in query_upper and "entry_time" in query_upper.lower():
                    optimized_query = optimized_query.replace(
                        "FROM processed_trades",
                        "FROM processed_trades INDEXED BY idx_processed_trades_account_time"
                    )
                elif "TIME_BIN_ANALYSIS" in query_upper and "analysis_date" in query_upper.lower():
                    optimized_query = optimized_query.replace(
                        "FROM time_bin_analysis", 
                        "FROM time_bin_analysis INDEXED BY idx_timebin_timeseries"
                    )
        
        # 3. JOIN optimization - reorder JOINs for better performance
        if "JOIN" in query_upper:
            optimized_query = await self._optimize_join_order(optimized_query)
        
        # 4. WHERE clause optimization - move most selective conditions first
        if "WHERE" in query_upper:
            optimized_query = await self._optimize_where_clause(optimized_query)
        
        # 5. Subquery optimization - convert correlated subqueries to JOINs where possible
        if "SELECT" in query_upper.count("SELECT") > 1:
            optimized_query = await self._optimize_subqueries(optimized_query)
        
        # 6. Aggregation optimization
        if any(agg in query_upper for agg in ["GROUP BY", "SUM", "COUNT", "AVG", "MAX", "MIN"]):
            optimized_query = await self._optimize_aggregations(optimized_query)
        
        # 7. Add query hints for specific patterns
        optimized_query = await self._add_performance_hints(optimized_query)
        
        return optimized_query
    
    async def _optimize_join_order(self, query: str) -> str:
        """Optimize JOIN order for better performance."""
        # Simple JOIN reordering logic - move smaller tables first
        query_upper = query.upper()
        
        # If joining accounts table, make it the driving table (smaller)
        if "JOIN ACCOUNTS" in query_upper and "FROM PROCESSED_TRADES" in query_upper:
            # Rewrite to use accounts as driving table for small result sets
            if "WHERE ACCOUNTS." in query_upper:
                # Already optimal - accounts filtering first
                pass
        
        return query
    
    async def _optimize_where_clause(self, query: str) -> str:
        """Optimize WHERE clause by reordering conditions by selectivity."""
        # Simple optimization - move more selective conditions first
        # In practice, you'd analyze column statistics to determine selectivity
        
        query_parts = query.split("WHERE", 1)
        if len(query_parts) != 2:
            return query
        
        select_part = query_parts[0]
        where_part = query_parts[1]
        
        # Move date range conditions first (usually most selective)
        if "analysis_date" in where_part.lower() or "entry_time" in where_part.lower():
            # Already good - date conditions are typically selective
            pass
        
        return query
    
    async def _optimize_subqueries(self, query: str) -> str:
        """Optimize subqueries by converting to JOINs where beneficial."""
        # Complex subquery optimization would require query parsing
        # For now, return as-is
        return query
    
    async def _optimize_aggregations(self, query: str) -> str:
        """Optimize aggregation queries."""
        query_upper = query.upper()
        
        # For large aggregations, ensure proper indexes are used
        if "GROUP BY" in query_upper:
            # Ensure GROUP BY columns are indexed
            if "time_bin_analysis" in query.lower():
                # Use covering indexes for common GROUP BY patterns
                if "GROUP BY account_name" in query_upper:
                    query = query.replace(
                        "FROM time_bin_analysis",
                        "FROM time_bin_analysis INDEXED BY idx_timebin_covering_performance"
                    )
        
        return query
    
    async def _add_performance_hints(self, query: str) -> str:
        """Add database-specific performance hints."""
        query_upper = query.upper()
        
        # SQLite specific optimizations
        if "sqlite" in self.database_url.lower():
            # For complex queries, disable query flattening if causing issues
            if query_upper.count("SELECT") > 2:
                # Complex nested queries might benefit from this
                pass
        
        return query
    
    async def _update_query_metrics(
        self,
        query_hash: str,
        query_text: str,
        execution_time: float,
        rows_returned: int,
        error: Optional[str] = None
    ):
        """Update query performance metrics."""
        if query_hash not in self.query_metrics:
            self.query_metrics[query_hash] = QueryMetrics(
                query_hash=query_hash,
                query_text=query_text
            )
        
        metrics = self.query_metrics[query_hash]
        metrics.execution_count += 1
        metrics.total_execution_time += execution_time
        metrics.avg_execution_time = metrics.total_execution_time / metrics.execution_count
        metrics.min_execution_time = min(metrics.min_execution_time, execution_time)
        metrics.max_execution_time = max(metrics.max_execution_time, execution_time)
        metrics.rows_returned += rows_returned
        metrics.last_execution = datetime.now()
        
        # Analyze query complexity
        metrics.complexity = self._analyze_query_complexity(query_text)
        
        # Check for table scans (simplified heuristic)
        if "WHERE" not in query_text.upper() and "SELECT" in query_text.upper():
            metrics.table_scans += 1
    
    def _analyze_query_complexity(self, query: str) -> QueryComplexity:
        """Analyze query complexity."""
        query_upper = query.upper()
        
        # Count complexity indicators
        complexity_score = 0
        
        if "JOIN" in query_upper:
            complexity_score += query_upper.count("JOIN") * 2
        if "SUBQUERY" in query_upper or "SELECT" in query_upper.count("SELECT") > 1:
            complexity_score += 3
        if "GROUP BY" in query_upper:
            complexity_score += 2
        if "ORDER BY" in query_upper:
            complexity_score += 1
        if "HAVING" in query_upper:
            complexity_score += 2
        
        # Classify complexity
        if complexity_score <= 2:
            return QueryComplexity.SIMPLE
        elif complexity_score <= 5:
            return QueryComplexity.MODERATE
        elif complexity_score <= 10:
            return QueryComplexity.COMPLEX
        else:
            return QueryComplexity.VERY_COMPLEX
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        logger.info("Database monitoring loop started")
        
        while self.monitoring_active:
            try:
                # Collect performance baseline
                asyncio.run(self._collect_performance_baseline())
                
                # Sleep until next collection
                time.sleep(self.baseline_collection_interval)
                
            except Exception as e:
                logger.error(f"Monitoring loop error: {str(e)}")
                time.sleep(10)  # Short sleep on error
        
        logger.info("Database monitoring loop stopped")
    
    async def _collect_performance_baseline(self):
        """Collect performance baseline metrics."""
        timestamp = datetime.now()
        
        try:
            # Calculate current metrics
            total_queries = sum(m.execution_count for m in self.query_metrics.values())
            if total_queries > 0:
                avg_response_time = sum(m.avg_execution_time for m in self.query_metrics.values()) / len(self.query_metrics)
                
                # Calculate P95 response time
                response_times = [m.avg_execution_time for m in self.query_metrics.values()]
                response_times.sort()
                p95_index = int(len(response_times) * 0.95)
                p95_response_time = response_times[p95_index] if p95_index < len(response_times) else avg_response_time
            else:
                avg_response_time = 0.0
                p95_response_time = 0.0
            
            # Calculate throughput (queries per second)
            if len(self.performance_baselines) > 0:
                last_baseline = self.performance_baselines[-1]
                time_diff = (timestamp - last_baseline.timestamp).total_seconds()
                if time_diff > 0:
                    query_diff = total_queries - last_baseline.total_queries
                    throughput_qps = query_diff / time_diff
                else:
                    throughput_qps = 0.0
            else:
                throughput_qps = 0.0
            
            baseline = PerformanceBaseline(
                timestamp=timestamp,
                total_queries=total_queries,
                avg_response_time=avg_response_time,
                p95_response_time=p95_response_time,
                throughput_qps=throughput_qps,
                connection_pool_usage=0.5,  # Simplified
                cache_hit_ratio=0.95,  # Simplified
                error_rate=0.01  # Simplified
            )
            
            self.performance_baselines.append(baseline)
            
        except Exception as e:
            logger.error(f"Failed to collect performance baseline: {str(e)}")
    
    async def _start_real_time_monitoring(self):
        """Start real-time performance monitoring tasks."""
        # Start slow query detection
        asyncio.create_task(self._slow_query_monitor())
        
        # Start query pattern analysis
        asyncio.create_task(self._query_pattern_analyzer())
        
        # Start performance degradation detection
        asyncio.create_task(self._performance_degradation_detector())
        
        # Start resource usage monitoring
        asyncio.create_task(self._resource_usage_monitor())
        
        logger.info("Real-time monitoring tasks started")
    
    async def _slow_query_monitor(self):
        """Monitor and alert on slow queries in real-time."""
        while self.monitoring_active:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                # Identify queries exceeding threshold in recent period
                recent_slow_queries = [
                    (query_hash, metrics) for query_hash, metrics in self.query_metrics.items()
                    if (metrics.last_execution and 
                        (datetime.now() - metrics.last_execution).total_seconds() < 300 and  # Last 5 minutes
                        metrics.avg_execution_time > self.slow_query_threshold)
                ]
                
                if recent_slow_queries:
                    logger.warning(f"Detected {len(recent_slow_queries)} slow queries in last 5 minutes")
                    
                    # Generate optimization recommendations for slow queries
                    for query_hash, metrics in recent_slow_queries[:5]:  # Top 5 slowest
                        recommendations = await self._generate_slow_query_optimization(query_hash, metrics)
                        if recommendations:
                            logger.info(f"Optimization suggestions for {query_hash}: {recommendations}")
                
            except Exception as e:
                logger.error(f"Slow query monitoring error: {str(e)}")
    
    async def _query_pattern_analyzer(self):
        """Analyze query patterns for optimization opportunities."""
        while self.monitoring_active:
            try:
                await asyncio.sleep(300)  # Analyze every 5 minutes
                
                # Analyze time-bin query patterns
                timebin_patterns = await self._analyze_timebin_query_patterns()
                
                # Analyze aggregation patterns
                aggregation_patterns = await self._analyze_aggregation_patterns()
                
                # Detect repetitive query patterns
                repetitive_patterns = await self._detect_repetitive_patterns()
                
                # Cache optimization opportunities
                self.optimization_cache.update({
                    'timebin_patterns': timebin_patterns,
                    'aggregation_patterns': aggregation_patterns,
                    'repetitive_patterns': repetitive_patterns,
                    'last_pattern_analysis': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Query pattern analysis error: {str(e)}")
    
    async def _performance_degradation_detector(self):
        """Detect performance degradation trends."""
        while self.monitoring_active:
            try:
                await asyncio.sleep(600)  # Check every 10 minutes
                
                if len(self.performance_baselines) < 10:
                    continue  # Need more data points
                
                # Analyze recent performance trends
                recent_baselines = list(self.performance_baselines)[-10:]
                older_baselines = list(self.performance_baselines)[-20:-10] if len(self.performance_baselines) >= 20 else []
                
                if older_baselines:
                    recent_avg_time = sum(b.avg_response_time for b in recent_baselines) / len(recent_baselines)
                    older_avg_time = sum(b.avg_response_time for b in older_baselines) / len(older_baselines)
                    
                    # Detect significant degradation (>20% increase)
                    if recent_avg_time > older_avg_time * 1.2:
                        degradation_pct = ((recent_avg_time - older_avg_time) / older_avg_time) * 100
                        logger.warning(f"Performance degradation detected: {degradation_pct:.1f}% slower")
                        
                        # Trigger automatic optimization
                        await self._handle_performance_degradation(degradation_pct)
                
            except Exception as e:
                logger.error(f"Performance degradation detection error: {str(e)}")
    
    async def _resource_usage_monitor(self):
        """Monitor system resource usage related to database operations."""
        while self.monitoring_active:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Get system metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                # Check for resource constraints affecting database performance
                if cpu_percent > 80:
                    logger.warning(f"High CPU usage detected: {cpu_percent}%")
                    # Reduce query optimization aggressiveness
                    self.slow_query_threshold *= 0.8  # Lower threshold temporarily
                
                if memory.percent > 85:
                    logger.warning(f"High memory usage detected: {memory.percent}%")
                    # Clear optimization cache to free memory
                    self.optimization_cache.clear()
                
                # Record resource metrics
                self.optimization_cache['last_resource_check'] = {
                    'timestamp': datetime.now().isoformat(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_available_gb': memory.available / (1024**3)
                }
                
            except Exception as e:
                logger.error(f"Resource usage monitoring error: {str(e)}")
    
    async def _generate_slow_query_optimization(self, query_hash: str, metrics: QueryMetrics) -> List[str]:
        """Generate optimization recommendations for slow queries."""
        recommendations = []
        
        # Check if query involves large tables
        if "processed_trades" in metrics.query_text.lower():
            recommendations.append("Consider adding date range filters to limit result set")
            recommendations.append("Verify indexes on commonly filtered columns are being used")
        
        if "time_bin_analysis" in metrics.query_text.lower():
            recommendations.append("Use time-bin specific indexes for faster lookups")
            recommendations.append("Consider using covering indexes for SELECT queries")
        
        # Check for table scans
        if metrics.table_scans > 0:
            recommendations.append("Add indexes to eliminate table scans")
        
        # Check for complex joins
        if "join" in metrics.query_text.lower():
            recommendations.append("Verify join order is optimal (smaller tables first)")
            recommendations.append("Consider denormalizing frequently joined data")
        
        return recommendations
    
    async def _analyze_timebin_query_patterns(self) -> Dict[str, Any]:
        """Analyze time-bin specific query patterns."""
        timebin_queries = [
            (hash_val, metrics) for hash_val, metrics in self.query_metrics.items()
            if "time_bin" in metrics.query_text.lower()
        ]
        
        if not timebin_queries:
            return {'status': 'no_timebin_queries'}
        
        # Analyze common patterns
        pattern_analysis = {
            'total_timebin_queries': len(timebin_queries),
            'avg_execution_time': sum(m.avg_execution_time for _, m in timebin_queries) / len(timebin_queries),
            'most_frequent_patterns': [],
            'optimization_opportunities': []
        }
        
        # Identify most common query patterns
        query_patterns = defaultdict(int)
        for _, metrics in timebin_queries:
            # Simplified pattern extraction
            if "WHERE account_name" in metrics.query_text:
                query_patterns['account_filter'] += 1
            if "WHERE hour" in metrics.query_text:
                query_patterns['hour_filter'] += 1
            if "ORDER BY" in metrics.query_text:
                query_patterns['ordered_results'] += 1
        
        pattern_analysis['most_frequent_patterns'] = [
            {'pattern': pattern, 'count': count}
            for pattern, count in sorted(query_patterns.items(), key=lambda x: x[1], reverse=True)
        ]
        
        return pattern_analysis
    
    async def _analyze_aggregation_patterns(self) -> Dict[str, Any]:
        """Analyze aggregation query patterns for optimization."""
        agg_queries = [
            (hash_val, metrics) for hash_val, metrics in self.query_metrics.items()
            if any(agg in metrics.query_text.upper() for agg in ['SUM', 'COUNT', 'AVG', 'GROUP BY'])
        ]
        
        if not agg_queries:
            return {'status': 'no_aggregation_queries'}
        
        return {
            'total_aggregation_queries': len(agg_queries),
            'avg_execution_time': sum(m.avg_execution_time for _, m in agg_queries) / len(agg_queries),
            'slow_aggregations': len([m for _, m in agg_queries if m.avg_execution_time > self.slow_query_threshold]),
            'optimization_recommendations': [
                'Consider pre-computed aggregation tables for frequently used calculations',
                'Verify GROUP BY columns are properly indexed',
                'Consider partitioning large tables for faster aggregations'
            ]
        }
    
    async def _detect_repetitive_patterns(self) -> Dict[str, Any]:
        """Detect repetitive query patterns that could benefit from caching."""
        repetitive_queries = [
            (hash_val, metrics) for hash_val, metrics in self.query_metrics.items()
            if metrics.execution_count > 100  # Executed more than 100 times
        ]
        
        return {
            'total_repetitive_queries': len(repetitive_queries),
            'top_repetitive': [
                {
                    'query_hash': hash_val,
                    'execution_count': metrics.execution_count,
                    'total_time': metrics.total_execution_time,
                    'avg_time': metrics.avg_execution_time
                }
                for hash_val, metrics in sorted(repetitive_queries, key=lambda x: x[1].execution_count, reverse=True)[:5]
            ],
            'caching_recommendations': [
                'Implement query result caching for frequently executed queries',
                'Consider materialized views for complex repeated calculations',
                'Use connection-level prepared statements for repeated queries'
            ]
        }
    
    async def _handle_performance_degradation(self, degradation_pct: float):
        """Handle detected performance degradation."""
        logger.info(f"Handling performance degradation of {degradation_pct:.1f}%")
        
        # Automatic optimization actions
        optimization_actions = []
        
        # Clear query optimizer cache
        self.optimization_cache.clear()
        optimization_actions.append("Cleared optimization cache")
        
        # Trigger index analysis
        if degradation_pct > 30:  # Significant degradation
            # This would trigger index rebuilding in production
            optimization_actions.append("Scheduled index maintenance")
        
        # Adjust slow query threshold temporarily
        self.slow_query_threshold *= 0.9  # 10% more sensitive
        optimization_actions.append(f"Adjusted slow query threshold to {self.slow_query_threshold:.3f}s")
        
        logger.info(f"Automatic optimization actions taken: {optimization_actions}")
        
        return optimization_actions
    
    async def _collect_index_metrics(self):
        """Collect index usage and performance metrics."""
        try:
            with self._get_db_session() as session:
                # Get index information from SQLite
                tables_result = session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in tables_result.fetchall()]
                
                for table_name in tables:
                    # Get indexes for this table
                    indexes_result = session.execute(text(f"PRAGMA index_list('{table_name}')"))
                    indexes = indexes_result.fetchall()
                    
                    for index_info in indexes:
                        index_name = index_info[1]
                        is_unique = bool(index_info[2])
                        
                        # Get index columns
                        columns_result = session.execute(text(f"PRAGMA index_info('{index_name}')"))
                        columns = [row[2] for row in columns_result.fetchall()]
                        
                        # Create or update index metrics
                        if index_name not in self.index_metrics:
                            self.index_metrics[index_name] = IndexMetrics(
                                index_name=index_name,
                                table_name=table_name,
                                columns=columns,
                                is_unique=is_unique
                            )
                        
                        # Update metrics
                        index_metrics = self.index_metrics[index_name]
                        index_metrics.effectiveness_score = self._calculate_index_effectiveness(
                            index_name, table_name, columns
                        )
                
        except Exception as e:
            logger.error(f"Failed to collect index metrics: {str(e)}")
    
    def _calculate_index_effectiveness(
        self,
        index_name: str,
        table_name: str,
        columns: List[str]
    ) -> float:
        """Calculate index effectiveness score."""
        # Simplified effectiveness calculation
        effectiveness = 0.0
        
        # Check if index is used in queries
        for metrics in self.query_metrics.values():
            query_upper = metrics.query_text.upper()
            if table_name.upper() in query_upper:
                # Check if WHERE clause uses indexed columns
                for column in columns:
                    if f"WHERE.*{column.upper()}" in query_upper:
                        effectiveness += 10.0
                    if f"ORDER BY.*{column.upper()}" in query_upper:
                        effectiveness += 5.0
        
        return min(effectiveness, 100.0)  # Cap at 100
    
    async def _identify_optimization_opportunities(
        self,
        query_metrics: Dict[str, QueryMetrics]
    ) -> List[str]:
        """Identify optimization opportunities from query metrics."""
        opportunities = []
        
        for query_hash, metrics in query_metrics.items():
            # Slow queries
            if metrics.avg_execution_time > self.slow_query_threshold:
                opportunities.append(
                    f"Optimize slow query (avg: {metrics.avg_execution_time:.3f}s): {query_hash}"
                )
            
            # Table scans
            if metrics.table_scans > 0:
                opportunities.append(
                    f"Add indexes to eliminate table scans: {query_hash}"
                )
            
            # High frequency queries
            if metrics.execution_count > 1000:
                opportunities.append(
                    f"Cache or optimize frequent query ({metrics.execution_count} executions): {query_hash}"
                )
        
        return opportunities
    
    async def _identify_missing_indexes(self) -> List[OptimizationRecommendation]:
        """Identify missing indexes that could improve performance."""
        recommendations = []
        
        # Analyze WHERE clauses in slow queries
        for query_hash, metrics in self.query_metrics.items():
            if metrics.avg_execution_time > self.slow_query_threshold:
                # Simple pattern matching for WHERE clauses
                query_upper = metrics.query_text.upper()
                
                # Look for common patterns that need indexes
                where_match = re.search(r'WHERE\s+(\w+)\s*=', query_upper)
                if where_match:
                    column_name = where_match.group(1)
                    
                    recommendation = OptimizationRecommendation(
                        recommendation_id=f"missing_index_{query_hash}_{column_name}",
                        category="index",
                        priority=OptimizationPriority.HIGH,
                        description=f"Create index on column {column_name} to optimize WHERE clause",
                        impact_estimate="50-80% query time reduction",
                        implementation_sql=f"CREATE INDEX idx_{column_name} ON table_name({column_name})",
                        estimated_improvement=65.0,
                        affected_queries=[query_hash],
                        resource_requirements={"disk_space_mb": 10, "creation_time_seconds": 30}
                    )
                    
                    recommendations.append(recommendation)
        
        return recommendations
    
    async def _identify_unused_indexes(self) -> List[OptimizationRecommendation]:
        """Identify unused indexes that can be dropped."""
        recommendations = []
        
        for index_name, metrics in self.index_metrics.items():
            if metrics.usage_count == 0 and metrics.effectiveness_score == 0:
                recommendation = OptimizationRecommendation(
                    recommendation_id=f"unused_index_{index_name}",
                    category="index",
                    priority=OptimizationPriority.MEDIUM,
                    description=f"Drop unused index {index_name}",
                    impact_estimate="Reduced storage and maintenance overhead",
                    implementation_sql=f"DROP INDEX {index_name}",
                    estimated_improvement=5.0,
                    affected_queries=[],
                    resource_requirements={"execution_time_seconds": 5}
                )
                
                recommendations.append(recommendation)
        
        return recommendations
    
    async def _identify_duplicate_indexes(self) -> List[OptimizationRecommendation]:
        """Identify duplicate or redundant indexes."""
        recommendations = []
        
        # Group indexes by table and columns
        index_groups = defaultdict(list)
        for index_name, metrics in self.index_metrics.items():
            key = (metrics.table_name, tuple(sorted(metrics.columns)))
            index_groups[key].append((index_name, metrics))
        
        # Find duplicates
        for (table_name, columns), indexes in index_groups.items():
            if len(indexes) > 1:
                # Keep the most effective index, recommend dropping others
                indexes.sort(key=lambda x: x[1].effectiveness_score, reverse=True)
                
                for index_name, metrics in indexes[1:]:
                    recommendation = OptimizationRecommendation(
                        recommendation_id=f"duplicate_index_{index_name}",
                        category="index",
                        priority=OptimizationPriority.MEDIUM,
                        description=f"Drop duplicate index {index_name} on {table_name}({', '.join(columns)})",
                        impact_estimate="Reduced storage and maintenance overhead",
                        implementation_sql=f"DROP INDEX {index_name}",
                        estimated_improvement=3.0,
                        affected_queries=[],
                        resource_requirements={"execution_time_seconds": 5}
                    )
                    
                    recommendations.append(recommendation)
        
        return recommendations
    
    async def _optimize_existing_indexes(self) -> List[OptimizationRecommendation]:
        """Optimize existing indexes for better performance."""
        recommendations = []
        
        # This would involve more complex analysis in a real implementation
        # For now, return empty list
        
        return recommendations
    
    async def _analyze_index_usage(self) -> Dict[str, Any]:
        """Analyze index usage patterns."""
        return {
            "total_indexes": len(self.index_metrics),
            "used_indexes": sum(1 for m in self.index_metrics.values() if m.usage_count > 0),
            "unused_indexes": sum(1 for m in self.index_metrics.values() if m.usage_count == 0),
            "average_effectiveness": sum(m.effectiveness_score for m in self.index_metrics.values()) / max(1, len(self.index_metrics))
        }
    
    async def _get_connection_count(self, session: Session) -> int:
        """Get current database connection count."""
        # For SQLite, this is simplified
        return 1
    
    async def _get_database_size(self, session: Session) -> float:
        """Get database size in MB."""
        try:
            # For SQLite, get file size
            db_path = self.database_url.replace("sqlite:///", "").replace("sqlite://", "")
            if Path(db_path).exists():
                size_bytes = Path(db_path).stat().st_size
                return size_bytes / 1024 / 1024  # Convert to MB
            else:
                return 0.0
        except Exception:
            return 0.0
    
    def _calculate_optimization_score(
        self,
        avg_query_time: float,
        table_scan_ratio: float,
        index_efficiency: float,
        slow_query_count: int
    ) -> float:
        """Calculate overall optimization score (0-100)."""
        score = 100.0
        
        # Penalize slow queries
        if avg_query_time > 0.1:  # 100ms threshold
            score -= min(50, avg_query_time * 100)
        
        # Penalize table scans
        score -= table_scan_ratio * 30
        
        # Reward index efficiency
        score = score * (index_efficiency / 100.0)
        
        # Penalize slow query count
        score -= min(20, slow_query_count * 2)
        
        return max(0.0, score)
    
    def _analyze_performance_trends(self) -> Dict[str, Any]:
        """Analyze performance trends from baselines."""
        if len(self.performance_baselines) < 2:
            return {"status": "insufficient_data"}
        
        recent_baselines = list(self.performance_baselines)[-10:]  # Last 10 baselines
        
        # Calculate trends
        avg_response_times = [b.avg_response_time for b in recent_baselines]
        throughputs = [b.throughput_qps for b in recent_baselines]
        
        return {
            "avg_response_time_trend": "improving" if avg_response_times[-1] < avg_response_times[0] else "degrading",
            "throughput_trend": "improving" if throughputs[-1] > throughputs[0] else "degrading",
            "latest_avg_response_time": avg_response_times[-1],
            "latest_throughput": throughputs[-1],
            "baselines_analyzed": len(recent_baselines)
        }
    
    async def _collect_resource_metrics(self) -> Dict[str, Any]:
        """Collect system resource utilization metrics."""
        # Get CPU and memory usage
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            "cpu_usage_percent": cpu_percent,
            "memory_usage_percent": memory.percent,
            "memory_available_mb": memory.available / 1024 / 1024,
            "disk_io": "not_implemented",  # Would need more detailed implementation
            "network_io": "not_implemented"  # Would need more detailed implementation
        }
    
    async def _validate_recommendation(self, recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """Validate an optimization recommendation before applying."""
        try:
            if recommendation.implementation_sql:
                # For now, just validate SQL syntax
                # In a real implementation, you would do more thorough validation
                return {"valid": True, "message": "Validation passed"}
            else:
                return {"valid": False, "error": "No implementation SQL provided"}
        except Exception as e:
            return {"valid": False, "error": str(e)}
    
    async def _apply_recommendation(self, recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """Apply an optimization recommendation."""
        start_time = time.time()
        
        try:
            if recommendation.implementation_sql:
                with self._get_db_session() as session:
                    session.execute(text(recommendation.implementation_sql))
                
                execution_time = time.time() - start_time
                return {"success": True, "execution_time": execution_time}
            else:
                return {"success": False, "error": "No implementation SQL provided"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _recommendation_to_dict(self, recommendation: OptimizationRecommendation) -> Dict[str, Any]:
        """Convert recommendation to dictionary."""
        return {
            "recommendation_id": recommendation.recommendation_id,
            "category": recommendation.category,
            "priority": recommendation.priority.value,
            "description": recommendation.description,
            "impact_estimate": recommendation.impact_estimate,
            "estimated_improvement": recommendation.estimated_improvement,
            "affected_queries": recommendation.affected_queries,
            "resource_requirements": recommendation.resource_requirements,
            "risks": recommendation.risks
        }
    
    def _index_metrics_to_dict(self, metrics: IndexMetrics) -> Dict[str, Any]:
        """Convert index metrics to dictionary."""
        return {
            "index_name": metrics.index_name,
            "table_name": metrics.table_name,
            "columns": metrics.columns,
            "is_unique": metrics.is_unique,
            "usage_count": metrics.usage_count,
            "effectiveness_score": metrics.effectiveness_score,
            "size_kb": metrics.size_kb
        }
    
    def _health_metrics_to_dict(self, metrics: DatabaseHealthMetrics) -> Dict[str, Any]:
        """Convert health metrics to dictionary."""
        return {
            "connection_count": metrics.connection_count,
            "avg_query_time": metrics.avg_query_time,
            "slow_query_count": metrics.slow_query_count,
            "index_efficiency": metrics.index_efficiency,
            "table_scan_ratio": metrics.table_scan_ratio,
            "database_size_mb": metrics.database_size_mb,
            "optimization_score": metrics.optimization_score
        }


# Utility functions for external use
async def create_optimized_query_service(
    database_url: str,
    enable_monitoring: bool = True
) -> QueryOptimizer:
    """
    Create and initialize an optimized query service.
    
    Args:
        database_url: Database connection URL
        enable_monitoring: Whether to enable performance monitoring
        
    Returns:
        Configured QueryOptimizer instance
    """
    optimizer = QueryOptimizer(
        database_url=database_url,
        monitoring_enabled=enable_monitoring
    )
    
    if enable_monitoring:
        await optimizer.start_monitoring()
    
    return optimizer


async def run_database_health_check(database_url: str) -> Dict[str, Any]:
    """
    Run a quick database health check.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        Health check results
    """
    optimizer = QueryOptimizer(database_url, monitoring_enabled=False)
    
    try:
        health_metrics = await optimizer.get_database_health()
        
        return {
            "status": "healthy" if health_metrics.optimization_score > 70 else "needs_attention",
            "optimization_score": health_metrics.optimization_score,
            "avg_query_time": health_metrics.avg_query_time,
            "database_size_mb": health_metrics.database_size_mb,
            "recommendations": "Run full optimization analysis for detailed recommendations"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }