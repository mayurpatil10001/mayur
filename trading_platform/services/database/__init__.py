"""
Database optimization and management services.

This module provides comprehensive database optimization capabilities including:
- Query optimization and performance monitoring
- Connection pool management and optimization
- Database health monitoring and metrics
- Automated optimization recommendations
"""

from .query_optimizer import (
    QueryOptimizer, QueryMetrics, IndexMetrics, OptimizationRecommendation,
    DatabaseHealthMetrics, PerformanceBaseline, QueryComplexity, OptimizationPriority,
    create_optimized_query_service, run_database_health_check
)

from .connection_pool_manager import (
    ConnectionPoolManager, PoolConfiguration, PoolStrategy, ConnectionState,
    ConnectionMetrics, PoolMetrics, OptimizationEvent,
    create_optimized_pool_manager, run_pool_health_check
)

__all__ = [
    # Query Optimizer
    'QueryOptimizer',
    'QueryMetrics',
    'IndexMetrics',
    'OptimizationRecommendation',
    'DatabaseHealthMetrics',
    'PerformanceBaseline',
    'QueryComplexity',
    'OptimizationPriority',
    'create_optimized_query_service',
    'run_database_health_check',
    
    # Connection Pool Manager
    'ConnectionPoolManager',
    'PoolConfiguration',
    'PoolStrategy',
    'ConnectionState',
    'ConnectionMetrics',
    'PoolMetrics',
    'OptimizationEvent',
    'create_optimized_pool_manager',
    'run_pool_health_check'
]