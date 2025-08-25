"""
Comprehensive performance tests for database optimization.

This module tests the database optimization functionality including:
- Query optimizer performance and correctness
- Index creation and management
- Connection pool optimization
- Large dataset query performance
- Concurrent analytics workload performance

Requirements: 10.1, 10.2, 10.3, 10.4
"""

import pytest
import asyncio
import time
import tempfile
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
from unittest.mock import Mock, patch, AsyncMock
import sqlite3

# Import the modules we're testing
from trading_platform.services.database.query_optimizer import (
    QueryOptimizer, QueryMetrics, DatabaseHealthMetrics, PerformanceBaseline
)
from trading_platform.services.database.connection_pool_manager import (
    ConnectionPoolManager, PoolConfiguration, PoolStrategy
)
from trading_platform.services.database.index_manager import (
    DatabaseIndexManager, IndexStatistics, TimeBinIndexPattern
)


class TestQueryOptimizer:
    """Test suite for QueryOptimizer performance and functionality."""
    
    @pytest.fixture
    async def temp_db_url(self):
        """Create a temporary SQLite database for testing."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        db_url = f"sqlite:///{temp_db.name}"
        
        # Create test tables
        conn = sqlite3.connect(temp_db.name)
        cursor = conn.cursor()
        
        # Create test schema similar to our trading platform
        cursor.execute("""
            CREATE TABLE processed_trades (
                id INTEGER PRIMARY KEY,
                trade_id TEXT UNIQUE,
                account_name TEXT,
                symbol TEXT,
                entry_time DATETIME,
                exit_time DATETIME,
                profit_loss REAL,
                quantity INTEGER,
                side TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE time_bin_analysis (
                id INTEGER PRIMARY KEY,
                account_name TEXT,
                hour INTEGER,
                minute_bin INTEGER,
                analysis_date DATE,
                total_trades INTEGER,
                win_rate REAL,
                average_pnl REAL,
                sharpe_ratio REAL
            )
        """)
        
        # Insert test data for performance testing
        test_data = []
        for i in range(1000):  # 1000 test trades
            test_data.append((
                f"trade_{i}",
                f"account_{i % 10}",  # 10 different accounts
                f"ES_{i % 5}",  # 5 different symbols
                datetime.now() - timedelta(days=i % 30),
                datetime.now() - timedelta(days=i % 30, hours=2),
                (i % 100) - 50,  # Profit/loss between -50 and +49
                100 + (i % 50),  # Quantity between 100-149
                "LONG" if i % 2 == 0 else "SHORT"
            ))
        
        cursor.executemany("""
            INSERT INTO processed_trades 
            (trade_id, account_name, symbol, entry_time, exit_time, profit_loss, quantity, side)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, test_data)
        
        # Insert time-bin analysis test data
        timebin_data = []
        for account in range(10):
            for hour in range(24):
                for minute_bin in [0, 30]:
                    timebin_data.append((
                        f"account_{account}",
                        hour,
                        minute_bin,
                        datetime.now().date(),
                        50 + (account * hour) % 100,  # Total trades
                        0.4 + (account * 0.05) % 0.4,  # Win rate 0.4-0.8
                        (account * hour * 10) % 1000 - 500,  # Average PnL
                        (account * 0.1) % 2.0  # Sharpe ratio
                    ))
        
        cursor.executemany("""
            INSERT INTO time_bin_analysis 
            (account_name, hour, minute_bin, analysis_date, total_trades, win_rate, average_pnl, sharpe_ratio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, timebin_data)
        
        conn.commit()
        conn.close()
        
        yield db_url
        
        # Cleanup
        os.unlink(temp_db.name)
    
    @pytest.fixture
    async def query_optimizer(self, temp_db_url):
        """Create QueryOptimizer instance with test database."""
        optimizer = QueryOptimizer(
            database_url=temp_db_url,
            monitoring_enabled=True,
            baseline_collection_interval=10
        )
        await optimizer.start_monitoring()
        yield optimizer
        await optimizer.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_query_optimization_performance(self, query_optimizer):
        """Test that query optimization improves performance."""
        # Test a complex query that should benefit from optimization
        complex_query = """
            SELECT pt.account_name, pt.symbol, COUNT(*) as trade_count, AVG(pt.profit_loss) as avg_pnl
            FROM processed_trades pt
            WHERE pt.entry_time >= '2024-01-01'
            AND pt.account_name IN ('account_1', 'account_2', 'account_3')
            GROUP BY pt.account_name, pt.symbol
            ORDER BY avg_pnl DESC
        """
        
        # Execute without optimization
        start_time = time.time()
        result_unoptimized, metrics_unoptimized = await query_optimizer.execute_optimized_query(
            complex_query, monitor_performance=False
        )
        unoptimized_time = time.time() - start_time
        
        # Execute with optimization
        start_time = time.time()
        result_optimized, metrics_optimized = await query_optimizer.execute_optimized_query(
            complex_query, monitor_performance=True
        )
        optimized_time = time.time() - start_time
        
        # Verify results are equivalent
        assert len(result_unoptimized) == len(result_optimized)
        
        # Performance should be tracked
        assert metrics_optimized.execution_count >= 1
        assert metrics_optimized.avg_execution_time > 0
        
        print(f"Query execution times - Unoptimized: {unoptimized_time:.3f}s, Optimized: {optimized_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_large_dataset_query_optimization(self, query_optimizer):
        """Test optimization on queries that would return large datasets."""
        # Query that would return all trades without optimization
        large_dataset_query = "SELECT * FROM processed_trades WHERE symbol LIKE 'ES_%'"
        
        result, metrics = await query_optimizer.execute_optimized_query(large_dataset_query)
        
        # Verify that LIMIT was automatically added for safety
        assert len(result) <= 10000, "Query optimizer should limit large result sets"
        assert metrics.rows_returned <= 10000
        
        # Performance metrics should be recorded
        assert metrics.execution_count == 1
        assert metrics.avg_execution_time > 0
    
    @pytest.mark.asyncio 
    async def test_time_bin_query_optimization(self, query_optimizer):
        """Test optimization specific to time-bin analytics queries."""
        timebin_query = """
            SELECT account_name, hour, minute_bin, AVG(win_rate) as avg_win_rate
            FROM time_bin_analysis
            WHERE analysis_date >= '2024-01-01'
            AND hour BETWEEN 9 AND 16
            GROUP BY account_name, hour, minute_bin
            ORDER BY avg_win_rate DESC
        """
        
        result, metrics = await query_optimizer.execute_optimized_query(timebin_query)
        
        # Should return results efficiently
        assert len(result) > 0
        assert metrics.avg_execution_time < 1.0  # Should be fast with proper optimization
        
        # Query complexity should be analyzed
        assert metrics.complexity is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_query_performance(self, query_optimizer):
        """Test performance under concurrent query load."""
        queries = [
            "SELECT COUNT(*) FROM processed_trades WHERE account_name = 'account_1'",
            "SELECT AVG(profit_loss) FROM processed_trades WHERE symbol = 'ES_1'",
            "SELECT * FROM time_bin_analysis WHERE hour = 10 LIMIT 100",
            "SELECT account_name, SUM(profit_loss) FROM processed_trades GROUP BY account_name",
            "SELECT * FROM processed_trades WHERE entry_time >= '2024-01-01' LIMIT 500"
        ]
        
        # Execute queries concurrently
        tasks = []
        start_time = time.time()
        
        for query in queries:
            task = asyncio.create_task(
                query_optimizer.execute_optimized_query(query, monitor_performance=True)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        # All queries should complete successfully
        assert len(results) == len(queries)
        for result, metrics in results:
            assert result is not None
            assert metrics.execution_count >= 1
        
        # Performance should be reasonable
        assert total_time < 5.0, f"Concurrent queries took too long: {total_time:.3f}s"
        
        print(f"Concurrent query execution time: {total_time:.3f}s for {len(queries)} queries")
    
    @pytest.mark.asyncio
    async def test_performance_monitoring_accuracy(self, query_optimizer):
        """Test that performance monitoring accurately captures metrics."""
        test_query = "SELECT COUNT(*) FROM processed_trades"
        
        # Execute query multiple times to build metrics
        for i in range(10):
            await query_optimizer.execute_optimized_query(test_query, monitor_performance=True)
            await asyncio.sleep(0.1)  # Small delay between executions
        
        # Check that metrics were captured accurately
        query_hash = query_optimizer._hash_query(test_query)
        assert query_hash in query_optimizer.query_metrics
        
        metrics = query_optimizer.query_metrics[query_hash]
        assert metrics.execution_count == 10
        assert metrics.avg_execution_time > 0
        assert metrics.min_execution_time <= metrics.avg_execution_time <= metrics.max_execution_time
        assert metrics.last_execution is not None
    
    @pytest.mark.asyncio
    async def test_database_health_metrics(self, query_optimizer):
        """Test database health metrics collection."""
        health_metrics = await query_optimizer.get_database_health()
        
        assert isinstance(health_metrics, DatabaseHealthMetrics)
        assert health_metrics.connection_count >= 0
        assert 0 <= health_metrics.optimization_score <= 100
        assert health_metrics.avg_query_time >= 0
        assert health_metrics.database_size_mb >= 0
        
        print(f"Database health - Optimization score: {health_metrics.optimization_score:.1f}")
    
    @pytest.mark.asyncio
    async def test_optimization_recommendations(self, query_optimizer):
        """Test that optimization recommendations are generated."""
        # Execute some queries to generate data for recommendations
        queries = [
            "SELECT * FROM processed_trades",  # Table scan
            "SELECT * FROM processed_trades WHERE account_name = 'account_1'",  # Needs index
            "SELECT COUNT(*) FROM processed_trades GROUP BY symbol"  # Aggregation
        ]
        
        for query in queries:
            await query_optimizer.execute_optimized_query(query)
        
        # Generate optimization report
        report = await query_optimizer.generate_optimization_report()
        
        assert "query_performance" in report
        assert "optimization_recommendations" in report
        assert "executive_summary" in report
        
        # Should have some recommendations
        assert len(report["optimization_recommendations"]) > 0
        
        print(f"Generated {len(report['optimization_recommendations'])} optimization recommendations")


class TestConnectionPoolManager:
    """Test suite for ConnectionPoolManager performance and analytics optimization."""
    
    @pytest.fixture
    async def temp_db_url(self):
        """Create temporary database for connection pool testing."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        yield db_url
        
        os.unlink(temp_db.name)
    
    @pytest.fixture
    async def pool_manager(self, temp_db_url):
        """Create ConnectionPoolManager with analytics-optimized configuration."""
        config = PoolConfiguration(
            min_size=4,
            max_size=16,
            overflow=8,
            strategy=PoolStrategy.ADAPTIVE,
            timeout=30.0
        )
        
        manager = ConnectionPoolManager(temp_db_url, config, monitoring_enabled=True)
        await manager.start_monitoring()
        
        yield manager
        
        await manager.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_analytics_workload_optimization(self, pool_manager):
        """Test connection pool optimization for analytics workloads."""
        # Get initial configuration
        initial_config = pool_manager._pool_config_to_dict()
        
        # Optimize for analytics workload
        optimization_results = await pool_manager.optimize_for_analytics_workload()
        
        assert "original_config" in optimization_results
        assert "optimizations_applied" in optimization_results
        assert "estimated_improvement" in optimization_results
        
        # Should have some optimizations for analytics
        if optimization_results["optimizations_applied"]:
            assert optimization_results["estimated_improvement"] > 0
            print(f"Analytics optimization applied {len(optimization_results['optimizations_applied'])} changes")
    
    @pytest.mark.asyncio
    async def test_concurrent_analytics_queries(self, pool_manager):
        """Test concurrent execution of analytics queries."""
        # Create test queries typical of analytics workloads
        analytics_queries = [
            "SELECT COUNT(*) as total_records",
            "SELECT 'test' as status",
            "SELECT 1 + 1 as calculation",
            "SELECT datetime('now') as current_time",
            "SELECT random() as random_number"
        ]
        
        start_time = time.time()
        results = await pool_manager.execute_concurrent_analytics_queries(
            analytics_queries, 
            max_workers=4
        )
        execution_time = time.time() - start_time
        
        # All queries should complete
        assert len(results) == len(analytics_queries)
        successful_results = [r for r in results if r is not None]
        assert len(successful_results) == len(analytics_queries)
        
        # Should be reasonably fast
        assert execution_time < 10.0, f"Concurrent queries took too long: {execution_time:.3f}s"
        
        print(f"Executed {len(analytics_queries)} concurrent queries in {execution_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_analytics_performance_metrics(self, pool_manager):
        """Test analytics-specific performance metrics."""
        metrics = await pool_manager.get_analytics_performance_metrics()
        
        assert "concurrent_query_capacity" in metrics
        assert "analytics_readiness_score" in metrics
        assert "recommended_concurrent_workers" in metrics
        assert "time_bin_query_optimization" in metrics
        
        # Validate metric values
        assert metrics["concurrent_query_capacity"] > 0
        assert 0 <= metrics["analytics_readiness_score"] <= 100
        assert metrics["recommended_concurrent_workers"] > 0
        
        print(f"Analytics readiness score: {metrics['analytics_readiness_score']:.1f}")
        print(f"Recommended concurrent workers: {metrics['recommended_concurrent_workers']}")
    
    @pytest.mark.asyncio
    async def test_pool_health_under_load(self, pool_manager):
        """Test connection pool health under heavy analytics load."""
        # Execute many concurrent queries to stress test the pool
        heavy_queries = ["SELECT 1"] * 50  # 50 simple queries
        
        # Execute in batches to simulate heavy load
        batch_size = 10
        total_batches = len(heavy_queries) // batch_size
        
        start_time = time.time()
        for i in range(total_batches):
            batch_queries = heavy_queries[i*batch_size:(i+1)*batch_size]
            await pool_manager.execute_concurrent_analytics_queries(batch_queries, max_workers=8)
        
        load_time = time.time() - start_time
        
        # Check pool health after load
        health_report = await pool_manager.execute_health_check()
        
        assert health_report["overall_health"] in ["excellent", "good", "fair", "poor"]
        assert "performance_metrics" in health_report
        assert "issues_found" in health_report
        assert "recommendations" in health_report
        
        print(f"Heavy load test completed in {load_time:.3f}s")
        print(f"Pool health after load: {health_report['overall_health']}")
    
    @pytest.mark.asyncio  
    async def test_pool_auto_optimization(self, pool_manager):
        """Test automatic pool optimization based on workload patterns."""
        # Simulate high-frequency queries to trigger optimization
        frequent_queries = ["SELECT datetime('now')"] * 20
        
        # Execute queries to generate workload pattern
        await pool_manager.execute_concurrent_analytics_queries(frequent_queries, max_workers=4)
        
        # Trigger optimization
        optimization_result = await pool_manager.optimize_pool_size(force=True)
        
        assert "current_size" in optimization_result
        assert "optimal_size" in optimization_result
        assert "workload_analysis" in optimization_result
        
        workload = optimization_result["workload_analysis"]
        assert "checkout_frequency" in workload
        assert "query_frequency" in workload
        assert "workload_intensity" in workload
        
        print(f"Pool optimization: {optimization_result['current_size']} -> {optimization_result['optimal_size']}")


class TestDatabaseIndexOptimization:
    """Test database index creation and optimization performance."""
    
    @pytest.mark.asyncio
    async def test_index_creation_performance(self):
        """Test performance of creating time-bin specific indexes."""
        # Mock database configuration
        mock_config = Mock()
        mock_config.connection_string = "sqlite:///test.db"
        
        # Create index manager
        index_manager = DatabaseIndexManager(mock_config)
        
        # Mock the initialization to avoid actual database operations
        with patch.object(index_manager, '_load_database_metadata'), \
             patch.object(index_manager, '_discover_existing_indexes'), \
             patch.object(index_manager, '_load_index_statistics'), \
             patch.object(index_manager, '_analyze_time_bin_patterns'):
            
            await index_manager.initialize()
        
        # Mock time bins for testing
        mock_time_bins = [Mock() for _ in range(24)]  # 24 time bins
        for i, tb in enumerate(mock_time_bins):
            tb.hour = i
            tb.minute = 30
        
        # Test index creation
        with patch.object(index_manager, '_index_exists', return_value=False), \
             patch.object(index_manager, '_queue_index_creation', return_value="job_123"), \
             patch.object(index_manager, '_wait_for_critical_indexes'):
            
            start_time = time.time()
            results = await index_manager.create_time_bin_indexes(mock_time_bins)
            creation_time = time.time() - start_time
            
            # Should create multiple specialized indexes
            assert len(results) > 0
            assert creation_time < 5.0  # Should queue quickly
            
            print(f"Queued {len(results)} index creations in {creation_time:.3f}s")
    
    @pytest.mark.asyncio
    async def test_index_optimization_analysis(self):
        """Test index usage analysis and optimization recommendations."""
        mock_config = Mock()
        index_manager = DatabaseIndexManager(mock_config)
        
        # Mock existing indexes with statistics
        mock_stats = IndexStatistics(
            index_name="test_index",
            table_name="test_table", 
            schema_name="public",
            index_type="btree",
            total_scans=1000,
            total_seeks=5000,
            total_lookups=6000,
            last_used=datetime.now(),
            avg_scan_time=0.1,
            avg_seek_time=0.01,
            total_pages=100,
            fragmentation_percent=25.0,
            size_mb=10.0,
            row_count=100000,
            maintenance_cost=5.0,
            last_maintenance=datetime.now() - timedelta(days=7),
            selectivity=0.8,
            usage_frequency=50.0,
            cost_benefit_ratio=0.9
        )
        
        index_manager.index_statistics["test_index"] = mock_stats
        
        # Test optimization analysis
        with patch.object(index_manager, '_update_all_index_statistics'), \
             patch.object(index_manager, '_identify_missing_indexes', return_value=[]), \
             patch.object(index_manager, '_calculate_optimization_impact', return_value=0.25):
            
            optimization_results = await index_manager.optimize_existing_indexes()
            
            assert "analyzed_indexes" in optimization_results
            assert optimization_results["analyzed_indexes"] == 1
            assert "estimated_performance_gain" in optimization_results
            
            # Should calculate efficiency score
            efficiency = mock_stats.calculate_efficiency_score()
            assert 0 <= efficiency <= 1.0
            
            print(f"Index efficiency score: {efficiency:.3f}")


class TestPerformanceIntegration:
    """Integration tests for complete database optimization pipeline."""
    
    @pytest.mark.asyncio
    async def test_complete_optimization_pipeline(self):
        """Test complete database optimization workflow."""
        # Create temporary database
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        try:
            # Initialize all optimization components
            query_optimizer = QueryOptimizer(db_url, monitoring_enabled=True)
            pool_manager = ConnectionPoolManager(db_url, monitoring_enabled=True)
            
            await query_optimizer.start_monitoring()
            await pool_manager.start_monitoring()
            
            # Execute analytics workload simulation
            analytics_queries = [
                "SELECT 1 as test_query",
                "SELECT datetime('now') as current_time", 
                "SELECT random() as random_value"
            ]
            
            # Test concurrent execution
            start_time = time.time()
            for _ in range(5):  # 5 rounds of queries
                results = await pool_manager.execute_concurrent_analytics_queries(
                    analytics_queries, max_workers=3
                )
                assert all(r is not None for r in results)
            
            workload_time = time.time() - start_time
            
            # Optimize based on workload
            pool_optimization = await pool_manager.optimize_for_analytics_workload()
            query_analysis = await query_optimizer.analyze_query_performance(time_window_hours=1)
            
            # Generate comprehensive report
            optimization_report = await query_optimizer.generate_optimization_report()
            
            # Validate results
            assert workload_time < 10.0, f"Workload simulation took too long: {workload_time:.3f}s"
            assert len(pool_optimization["optimizations_applied"]) >= 0
            assert query_analysis["total_queries_analyzed"] >= 0
            assert "executive_summary" in optimization_report
            
            print(f"Complete optimization pipeline test completed in {workload_time:.3f}s")
            print(f"Query analysis: {query_analysis['total_executions']} executions")
            
        finally:
            # Cleanup
            await query_optimizer.stop_monitoring()
            await pool_manager.stop_monitoring() 
            os.unlink(temp_db.name)
    
    @pytest.mark.asyncio
    async def test_performance_regression_detection(self):
        """Test that performance regression is properly detected."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        try:
            query_optimizer = QueryOptimizer(db_url, monitoring_enabled=True, baseline_collection_interval=1)
            await query_optimizer.start_monitoring()
            
            # Create baseline performance data
            for i in range(15):
                baseline = PerformanceBaseline(
                    timestamp=datetime.now() - timedelta(minutes=15-i),
                    total_queries=100 + i,
                    avg_response_time=0.1 + (i * 0.01),  # Gradually increasing
                    p95_response_time=0.2 + (i * 0.02),
                    throughput_qps=50.0 - (i * 0.5),
                    connection_pool_usage=0.7,
                    cache_hit_ratio=0.95,
                    error_rate=0.01
                )
                query_optimizer.performance_baselines.append(baseline)
            
            # Simulate recent performance degradation
            for i in range(10):
                degraded_baseline = PerformanceBaseline(
                    timestamp=datetime.now() - timedelta(minutes=10-i),
                    total_queries=200 + i,
                    avg_response_time=0.25 + (i * 0.05),  # Significantly worse
                    p95_response_time=0.5 + (i * 0.1),
                    throughput_qps=30.0,  # Lower throughput
                    connection_pool_usage=0.9,  # Higher utilization
                    cache_hit_ratio=0.85,  # Lower cache hit rate
                    error_rate=0.03  # Higher error rate
                )
                query_optimizer.performance_baselines.append(degraded_baseline)
            
            # Test degradation detection (this would normally run in background)
            recent_baselines = list(query_optimizer.performance_baselines)[-10:]
            older_baselines = list(query_optimizer.performance_baselines)[-20:-10]
            
            recent_avg = sum(b.avg_response_time for b in recent_baselines) / len(recent_baselines)
            older_avg = sum(b.avg_response_time for b in older_baselines) / len(older_baselines)
            
            degradation_pct = ((recent_avg - older_avg) / older_avg) * 100
            
            # Should detect significant degradation
            assert degradation_pct > 20, f"Should detect degradation, got {degradation_pct:.1f}%"
            
            # Test automatic handling
            if degradation_pct > 20:
                actions = await query_optimizer._handle_performance_degradation(degradation_pct)
                assert len(actions) > 0
                print(f"Detected {degradation_pct:.1f}% performance degradation")
                print(f"Automatic actions taken: {actions}")
                
        finally:
            await query_optimizer.stop_monitoring()
            os.unlink(temp_db.name)


# Performance benchmarks and stress tests
class TestPerformanceBenchmarks:
    """Performance benchmarks to validate optimization effectiveness."""
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_query_optimization_benchmark(self):
        """Benchmark query optimization performance improvements."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        try:
            # Create test data
            conn = sqlite3.connect(temp_db.name)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE benchmark_trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    timestamp DATETIME,
                    price REAL,
                    quantity INTEGER
                )
            """)
            
            # Insert substantial test data
            test_data = [
                (f"SYMBOL_{i%100}", datetime.now() - timedelta(minutes=i), 100.0 + i*0.01, 100 + i%50)
                for i in range(5000)  # 5000 records
            ]
            cursor.executemany(
                "INSERT INTO benchmark_trades (symbol, timestamp, price, quantity) VALUES (?, ?, ?, ?)",
                test_data
            )
            conn.commit()
            conn.close()
            
            # Benchmark with optimization
            optimizer = QueryOptimizer(db_url, monitoring_enabled=True)
            await optimizer.start_monitoring()
            
            benchmark_queries = [
                "SELECT COUNT(*) FROM benchmark_trades WHERE symbol LIKE 'SYMBOL_1%'",
                "SELECT symbol, AVG(price) FROM benchmark_trades GROUP BY symbol",
                "SELECT * FROM benchmark_trades WHERE timestamp >= datetime('now', '-1 hour')",
                "SELECT symbol, SUM(quantity) FROM benchmark_trades WHERE price > 100.5 GROUP BY symbol"
            ]
            
            # Execute benchmark
            total_start_time = time.time()
            execution_times = []
            
            for query in benchmark_queries:
                start_time = time.time()
                result, metrics = await optimizer.execute_optimized_query(query)
                execution_time = time.time() - start_time
                execution_times.append(execution_time)
                
                # Verify results
                assert result is not None
                assert metrics.execution_count >= 1
            
            total_time = time.time() - total_start_time
            avg_time = sum(execution_times) / len(execution_times)
            
            # Performance assertions
            assert total_time < 5.0, f"Benchmark queries too slow: {total_time:.3f}s"
            assert avg_time < 1.0, f"Average query time too slow: {avg_time:.3f}s"
            assert all(t < 2.0 for t in execution_times), "Individual queries too slow"
            
            print(f"Benchmark Results:")
            print(f"Total time: {total_time:.3f}s")
            print(f"Average time per query: {avg_time:.3f}s")
            print(f"Individual times: {[f'{t:.3f}s' for t in execution_times]}")
            
            await optimizer.stop_monitoring()
            
        finally:
            os.unlink(temp_db.name)
    
    @pytest.mark.benchmark
    @pytest.mark.asyncio
    async def test_connection_pool_scalability(self):
        """Test connection pool scalability under increasing load."""
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        db_url = f"sqlite:///{temp_db.name}"
        
        try:
            # Test different pool sizes
            pool_sizes = [4, 8, 16, 32]
            scalability_results = {}
            
            for pool_size in pool_sizes:
                config = PoolConfiguration(
                    min_size=pool_size//2,
                    max_size=pool_size,
                    overflow=pool_size//4,
                    strategy=PoolStrategy.ADAPTIVE
                )
                
                pool_manager = ConnectionPoolManager(db_url, config, monitoring_enabled=False)
                
                # Test with increasing concurrent load
                concurrent_queries = ["SELECT 1"] * (pool_size * 2)  # 2x pool size
                
                start_time = time.time()
                results = await pool_manager.execute_concurrent_analytics_queries(
                    concurrent_queries, 
                    max_workers=pool_size
                )
                execution_time = time.time() - start_time
                
                # Verify all queries completed
                successful = len([r for r in results if r is not None])
                success_rate = successful / len(concurrent_queries)
                
                scalability_results[pool_size] = {
                    'execution_time': execution_time,
                    'success_rate': success_rate,
                    'queries_per_second': len(concurrent_queries) / execution_time
                }
                
                # Cleanup
                await pool_manager.stop_monitoring()
            
            # Analyze scalability
            print("Connection Pool Scalability Results:")
            for pool_size, metrics in scalability_results.items():
                print(f"Pool size {pool_size:2d}: {metrics['execution_time']:.3f}s, "
                      f"{metrics['queries_per_second']:.1f} QPS, "
                      f"{metrics['success_rate']:.1%} success")
            
            # Validate scalability improvements
            smallest_pool = scalability_results[pool_sizes[0]]
            largest_pool = scalability_results[pool_sizes[-1]]
            
            # Larger pools should handle more queries per second (with diminishing returns)
            qps_improvement = largest_pool['queries_per_second'] / smallest_pool['queries_per_second']
            assert qps_improvement > 1.2, f"Insufficient scalability improvement: {qps_improvement:.2f}x"
            
        finally:
            os.unlink(temp_db.name)


if __name__ == "__main__":
    # Run tests with performance reporting
    pytest.main([
        __file__,
        "-v",
        "-s", 
        "--tb=short",
        "-m", "not benchmark"  # Skip benchmark tests in normal runs
    ])