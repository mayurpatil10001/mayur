"""
Comprehensive tests for the database query optimizer.

This module tests all aspects of the QueryOptimizer including:
- Query performance analysis
- Index optimization recommendations
- Database health monitoring
- Optimization report generation
"""

import pytest
import asyncio
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from trading_platform.services.database.query_optimizer import (
    QueryOptimizer, QueryMetrics, IndexMetrics, OptimizationRecommendation,
    DatabaseHealthMetrics, PerformanceBaseline, QueryComplexity, OptimizationPriority,
    create_optimized_query_service, run_database_health_check
)


class TestQueryOptimizer:
    """Test suite for QueryOptimizer class."""
    
    @pytest.fixture
    def temp_database_url(self):
        """Create a temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        database_url = f"sqlite:///{temp_file.name}"
        temp_file.close()
        
        yield database_url
        
        # Cleanup
        if os.path.exists(temp_file.name):
            os.unlink(temp_file.name)
    
    @pytest.fixture
    def query_optimizer(self, temp_database_url):
        """Create QueryOptimizer instance for testing."""
        return QueryOptimizer(
            database_url=temp_database_url,
            monitoring_enabled=False  # Disable for testing
        )
    
    @pytest.fixture
    def sample_query_metrics(self):
        """Create sample query metrics for testing."""
        return QueryMetrics(
            query_hash="test_hash_123",
            query_text="SELECT * FROM test_table WHERE id = ?",
            execution_count=10,
            total_execution_time=5.0,
            avg_execution_time=0.5,
            min_execution_time=0.1,
            max_execution_time=1.0,
            rows_returned=100,
            complexity=QueryComplexity.SIMPLE,
            last_execution=datetime.now()
        )
    
    @pytest.fixture
    def sample_index_metrics(self):
        """Create sample index metrics for testing."""
        return IndexMetrics(
            index_name="idx_test_id",
            table_name="test_table",
            columns=["id"],
            is_unique=True,
            usage_count=50,
            effectiveness_score=85.0
        )
    
    def test_query_optimizer_initialization(self, temp_database_url):
        """Test QueryOptimizer initialization."""
        optimizer = QueryOptimizer(temp_database_url)
        
        assert optimizer.database_url == temp_database_url
        assert optimizer.monitoring_enabled is True
        assert optimizer.engine is not None
        assert optimizer.SessionLocal is not None
        assert isinstance(optimizer.query_metrics, dict)
        assert isinstance(optimizer.index_metrics, dict)
        assert optimizer.slow_query_threshold == 1.0
    
    def test_hash_query(self, query_optimizer):
        """Test query hashing functionality."""
        query1 = "SELECT * FROM users WHERE id = 123"
        query2 = "SELECT * FROM users WHERE id = 456"
        query3 = "select * from users where id = 123"
        
        hash1 = query_optimizer._hash_query(query1)
        hash2 = query_optimizer._hash_query(query2)
        hash3 = query_optimizer._hash_query(query3)
        
        # Different values should produce same hash pattern
        assert hash1 == hash2
        # Case insensitive
        assert hash1 == hash3
        # Should be string
        assert isinstance(hash1, str)
    
    def test_analyze_query_complexity(self, query_optimizer):
        """Test query complexity analysis."""
        simple_query = "SELECT * FROM users"
        moderate_query = "SELECT * FROM users WHERE active = 1 ORDER BY name"
        complex_query = """
            SELECT u.name, COUNT(o.id) 
            FROM users u 
            JOIN orders o ON u.id = o.user_id 
            WHERE u.active = 1 
            GROUP BY u.id 
            HAVING COUNT(o.id) > 5
        """
        
        assert query_optimizer._analyze_query_complexity(simple_query) == QueryComplexity.SIMPLE
        assert query_optimizer._analyze_query_complexity(moderate_query) == QueryComplexity.MODERATE
        assert query_optimizer._analyze_query_complexity(complex_query) == QueryComplexity.COMPLEX
    
    @pytest.mark.asyncio
    async def test_update_query_metrics(self, query_optimizer, sample_query_metrics):
        """Test query metrics updating."""
        query_hash = "test_hash"
        query_text = "SELECT * FROM test"
        
        # First execution
        await query_optimizer._update_query_metrics(
            query_hash, query_text, 0.5, 10
        )
        
        assert query_hash in query_optimizer.query_metrics
        metrics = query_optimizer.query_metrics[query_hash]
        assert metrics.execution_count == 1
        assert metrics.avg_execution_time == 0.5
        assert metrics.rows_returned == 10
        
        # Second execution
        await query_optimizer._update_query_metrics(
            query_hash, query_text, 1.0, 20
        )
        
        metrics = query_optimizer.query_metrics[query_hash]
        assert metrics.execution_count == 2
        assert metrics.avg_execution_time == 0.75  # (0.5 + 1.0) / 2
        assert metrics.rows_returned == 30  # 10 + 20
    
    @pytest.mark.asyncio
    async def test_execute_optimized_query(self, query_optimizer):
        """Test optimized query execution."""
        # Create a simple test table
        with query_optimizer._get_db_session() as session:
            session.execute("CREATE TABLE test_table (id INTEGER, name TEXT)")
            session.execute("INSERT INTO test_table VALUES (1, 'test')")
        
        # Execute query
        query = "SELECT * FROM test_table WHERE id = ?"
        result, metrics = await query_optimizer.execute_optimized_query(
            query, {"id": 1}
        )
        
        assert result is not None
        assert isinstance(metrics, QueryMetrics)
        assert metrics.query_text == query
        assert metrics.execution_count >= 1
    
    @pytest.mark.asyncio
    async def test_analyze_query_performance_no_data(self, query_optimizer):
        """Test query performance analysis with no data."""
        analysis = await query_optimizer.analyze_query_performance()
        
        assert analysis["status"] == "no_data"
        assert "message" in analysis
    
    @pytest.mark.asyncio
    async def test_analyze_query_performance_with_data(self, query_optimizer):
        """Test query performance analysis with sample data."""
        # Add sample metrics
        query_hash = "test_hash"
        await query_optimizer._update_query_metrics(
            query_hash, "SELECT * FROM test", 2.0, 100  # Slow query
        )
        
        analysis = await query_optimizer.analyze_query_performance()
        
        assert "time_window_hours" in analysis
        assert "total_queries_analyzed" in analysis
        assert "slow_queries" in analysis
        assert len(analysis["slow_queries"]) > 0
        assert analysis["slow_queries"][0]["query_hash"] == query_hash
    
    @pytest.mark.asyncio
    async def test_collect_index_metrics(self, query_optimizer):
        """Test index metrics collection."""
        # Create test table with index
        with query_optimizer._get_db_session() as session:
            session.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
            session.execute("CREATE INDEX idx_test_name ON test_table(name)")
        
        await query_optimizer._collect_index_metrics()
        
        # Should have collected index information
        assert len(query_optimizer.index_metrics) > 0
        
        # Check for our test index
        index_names = [metrics.index_name for metrics in query_optimizer.index_metrics.values()]
        assert "idx_test_name" in index_names
    
    @pytest.mark.asyncio
    async def test_identify_missing_indexes(self, query_optimizer):
        """Test missing index identification."""
        # Add a slow query that could benefit from an index
        await query_optimizer._update_query_metrics(
            "slow_hash", "SELECT * FROM users WHERE email = 'test@example.com'", 5.0, 1
        )
        
        recommendations = await query_optimizer._identify_missing_indexes()
        
        # Should generate recommendations for missing indexes
        assert len(recommendations) > 0
        assert all(isinstance(r, OptimizationRecommendation) for r in recommendations)
        assert all(r.category == "index" for r in recommendations)
    
    @pytest.mark.asyncio
    async def test_identify_unused_indexes(self, query_optimizer):
        """Test unused index identification."""
        # Add an unused index metric
        unused_index = IndexMetrics(
            index_name="idx_unused",
            table_name="test_table",
            columns=["unused_column"],
            is_unique=False,
            usage_count=0,
            effectiveness_score=0.0
        )
        query_optimizer.index_metrics["idx_unused"] = unused_index
        
        recommendations = await query_optimizer._identify_unused_indexes()
        
        assert len(recommendations) > 0
        recommendation = recommendations[0]
        assert "unused" in recommendation.description.lower()
        assert "DROP INDEX" in recommendation.implementation_sql
    
    @pytest.mark.asyncio
    async def test_get_database_health(self, query_optimizer):
        """Test database health metrics collection."""
        health_metrics = await query_optimizer.get_database_health()
        
        assert isinstance(health_metrics, DatabaseHealthMetrics)
        assert health_metrics.connection_count >= 0
        assert 0 <= health_metrics.optimization_score <= 100
        assert health_metrics.database_size_mb >= 0.0
    
    @pytest.mark.asyncio
    async def test_optimize_indexes(self, query_optimizer):
        """Test index optimization process."""
        # Add sample data
        await query_optimizer._update_query_metrics(
            "test_hash", "SELECT * FROM users WHERE email = 'test'", 2.0, 10
        )
        
        recommendations = await query_optimizer.optimize_indexes()
        
        assert isinstance(recommendations, list)
        assert all(isinstance(r, OptimizationRecommendation) for r in recommendations)
    
    @pytest.mark.asyncio
    async def test_generate_optimization_report(self, query_optimizer):
        """Test optimization report generation."""
        # Add some sample data
        await query_optimizer._update_query_metrics(
            "test_hash", "SELECT * FROM test", 1.5, 50
        )
        
        report = await query_optimizer.generate_optimization_report()
        
        assert "report_timestamp" in report
        assert "executive_summary" in report
        assert "query_performance" in report
        assert "index_optimization" in report
        assert "database_health" in report
        assert "optimization_recommendations" in report
        
        # Check executive summary
        summary = report["executive_summary"]
        assert "optimization_score" in summary
        assert "total_recommendations" in summary
    
    @pytest.mark.asyncio
    async def test_apply_optimization_recommendations_dry_run(self, query_optimizer):
        """Test applying optimization recommendations in dry run mode."""
        # Create a test recommendation
        recommendation = OptimizationRecommendation(
            recommendation_id="test_rec_1",
            category="index",
            priority=OptimizationPriority.HIGH,
            description="Test recommendation",
            impact_estimate="50% improvement",
            implementation_sql="CREATE INDEX test_idx ON test_table(id)",
            estimated_improvement=50.0,
            affected_queries=["test_hash"],
            resource_requirements={}
        )
        
        query_optimizer.optimization_recommendations.append(recommendation)
        
        results = await query_optimizer.apply_optimization_recommendations(
            ["test_rec_1"], dry_run=True
        )
        
        assert "applied_recommendations" in results
        assert "failed_recommendations" in results
        assert len(results["applied_recommendations"]) == 1
        assert results["applied_recommendations"][0]["status"] == "validated"
    
    @pytest.mark.asyncio
    async def test_performance_baseline_collection(self, query_optimizer):
        """Test performance baseline collection."""
        # Add some metrics first
        await query_optimizer._update_query_metrics(
            "test_hash", "SELECT * FROM test", 0.5, 10
        )
        
        await query_optimizer._collect_performance_baseline()
        
        assert len(query_optimizer.performance_baselines) > 0
        baseline = query_optimizer.performance_baselines[-1]
        assert isinstance(baseline, PerformanceBaseline)
        assert baseline.total_queries >= 0
        assert baseline.avg_response_time >= 0.0
    
    def test_calculate_optimization_score(self, query_optimizer):
        """Test optimization score calculation."""
        # Test good performance
        score = query_optimizer._calculate_optimization_score(
            avg_query_time=0.05,  # Fast queries
            table_scan_ratio=0.1,  # Few table scans
            index_efficiency=90.0,  # High index efficiency
            slow_query_count=0  # No slow queries
        )
        assert score > 80  # Should be high score
        
        # Test poor performance
        score = query_optimizer._calculate_optimization_score(
            avg_query_time=2.0,  # Slow queries
            table_scan_ratio=0.8,  # Many table scans
            index_efficiency=20.0,  # Low index efficiency
            slow_query_count=10  # Many slow queries
        )
        assert score < 50  # Should be low score


class TestQueryMetrics:
    """Test suite for QueryMetrics class."""
    
    def test_query_metrics_initialization(self):
        """Test QueryMetrics initialization."""
        metrics = QueryMetrics(
            query_hash="test_hash",
            query_text="SELECT * FROM test"
        )
        
        assert metrics.query_hash == "test_hash"
        assert metrics.query_text == "SELECT * FROM test"
        assert metrics.execution_count == 0
        assert metrics.complexity == QueryComplexity.SIMPLE


class TestIndexMetrics:
    """Test suite for IndexMetrics class."""
    
    def test_index_metrics_initialization(self):
        """Test IndexMetrics initialization."""
        metrics = IndexMetrics(
            index_name="idx_test",
            table_name="test_table",
            columns=["id", "name"],
            is_unique=True
        )
        
        assert metrics.index_name == "idx_test"
        assert metrics.table_name == "test_table"
        assert metrics.columns == ["id", "name"]
        assert metrics.is_unique is True
        assert metrics.effectiveness_score == 0.0


class TestOptimizationRecommendation:
    """Test suite for OptimizationRecommendation class."""
    
    def test_optimization_recommendation_creation(self):
        """Test OptimizationRecommendation creation."""
        recommendation = OptimizationRecommendation(
            recommendation_id="rec_001",
            category="index",
            priority=OptimizationPriority.HIGH,
            description="Create missing index",
            impact_estimate="50-70% improvement",
            implementation_sql="CREATE INDEX idx_test ON table(column)",
            estimated_improvement=60.0,
            affected_queries=["query_1", "query_2"],
            resource_requirements={"disk_space_mb": 10}
        )
        
        assert recommendation.recommendation_id == "rec_001"
        assert recommendation.category == "index"
        assert recommendation.priority == OptimizationPriority.HIGH
        assert recommendation.estimated_improvement == 60.0
        assert len(recommendation.affected_queries) == 2


class TestUtilityFunctions:
    """Test suite for utility functions."""
    
    @pytest.mark.asyncio
    async def test_create_optimized_query_service(self):
        """Test optimized query service creation."""
        with tempfile.NamedTemporaryFile(suffix=".db") as temp_file:
            database_url = f"sqlite:///{temp_file.name}"
            
            optimizer = await create_optimized_query_service(
                database_url=database_url,
                enable_monitoring=False
            )
            
            assert isinstance(optimizer, QueryOptimizer)
            assert optimizer.database_url == database_url
    
    @pytest.mark.asyncio
    async def test_run_database_health_check(self):
        """Test database health check function."""
        with tempfile.NamedTemporaryFile(suffix=".db") as temp_file:
            database_url = f"sqlite:///{temp_file.name}"
            
            health_check = await run_database_health_check(database_url)
            
            assert "status" in health_check
            assert "optimization_score" in health_check
            assert health_check["status"] in ["healthy", "needs_attention", "error"]


class TestMonitoringIntegration:
    """Test suite for monitoring integration."""
    
    @pytest.fixture
    def monitoring_optimizer(self, temp_database_url):
        """Create QueryOptimizer with monitoring enabled."""
        return QueryOptimizer(
            database_url=temp_database_url,
            monitoring_enabled=True,
            baseline_collection_interval=1  # 1 second for testing
        )
    
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitoring_optimizer):
        """Test starting and stopping monitoring."""
        await monitoring_optimizer.start_monitoring()
        assert monitoring_optimizer.monitoring_active is True
        assert monitoring_optimizer.monitoring_thread is not None
        
        await monitoring_optimizer.stop_monitoring()
        assert monitoring_optimizer.monitoring_active is False
    
    @pytest.mark.asyncio
    async def test_monitoring_loop_error_handling(self, monitoring_optimizer):
        """Test monitoring loop error handling."""
        # Mock an error in the monitoring loop
        with patch.object(monitoring_optimizer, '_collect_performance_baseline', 
                         side_effect=Exception("Test error")):
            await monitoring_optimizer.start_monitoring()
            
            # Wait a short time to let the monitoring loop run
            await asyncio.sleep(0.1)
            
            await monitoring_optimizer.stop_monitoring()
            
            # Should not crash despite the error


class TestPerformanceOptimization:
    """Test suite for performance optimization features."""
    
    @pytest.fixture
    def optimizer_with_data(self, temp_database_url):
        """Create optimizer with sample performance data."""
        optimizer = QueryOptimizer(temp_database_url, monitoring_enabled=False)
        
        # Add sample query metrics
        optimizer.query_metrics["fast_query"] = QueryMetrics(
            query_hash="fast_query",
            query_text="SELECT id FROM users WHERE id = ?",
            execution_count=1000,
            total_execution_time=50.0,
            avg_execution_time=0.05,
            rows_returned=1000,
            last_execution=datetime.now()
        )
        
        optimizer.query_metrics["slow_query"] = QueryMetrics(
            query_hash="slow_query",
            query_text="SELECT * FROM orders o JOIN users u ON o.user_id = u.id",
            execution_count=10,
            total_execution_time=50.0,
            avg_execution_time=5.0,
            rows_returned=10000,
            table_scans=5,
            complexity=QueryComplexity.COMPLEX,
            last_execution=datetime.now()
        )
        
        return optimizer
    
    @pytest.mark.asyncio
    async def test_identify_optimization_opportunities(self, optimizer_with_data):
        """Test optimization opportunity identification."""
        opportunities = await optimizer_with_data._identify_optimization_opportunities(
            optimizer_with_data.query_metrics
        )
        
        assert len(opportunities) > 0
        # Should identify slow query
        assert any("slow query" in opp.lower() for opp in opportunities)
        # Should identify table scans
        assert any("table scan" in opp.lower() for opp in opportunities)
        # Should identify frequent query
        assert any("frequent query" in opp.lower() for opp in opportunities)
    
    @pytest.mark.asyncio
    async def test_performance_trends_analysis(self, optimizer_with_data):
        """Test performance trends analysis."""
        # Add performance baselines
        for i in range(5):
            baseline = PerformanceBaseline(
                timestamp=datetime.now() - timedelta(minutes=i),
                total_queries=100 + i * 10,
                avg_response_time=0.5 - i * 0.05,  # Improving
                p95_response_time=1.0 - i * 0.1,
                throughput_qps=10.0 + i * 2,
                connection_pool_usage=0.5,
                cache_hit_ratio=0.95,
                error_rate=0.01
            )
            optimizer_with_data.performance_baselines.append(baseline)
        
        trends = optimizer_with_data._analyze_performance_trends()
        
        assert "avg_response_time_trend" in trends
        assert "throughput_trend" in trends
        assert trends["avg_response_time_trend"] == "improving"
        assert trends["throughput_trend"] == "improving"


@pytest.fixture
def temp_database_url():
    """Create a temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    database_url = f"sqlite:///{temp_file.name}"
    temp_file.close()
    
    yield database_url
    
    # Cleanup
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])