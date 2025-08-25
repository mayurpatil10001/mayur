"""
Performance benchmarking tests for the trading optimization platform.

Tests system performance under various load conditions and measures
key performance indicators.

Requirements: 8.2, 8.4
"""

import pytest
import asyncio
import time
import statistics
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from trading_platform.api.main import app
from trading_platform.config import config
from trading_platform.services.data_ingestion import SierraChartIngestionService
from trading_platform.services.analytics import AnalyticsService
from trading_platform.services.recommendations import RecommendationEngine


class PerformanceBenchmark:
    """Helper class for performance measurements."""
    
    def __init__(self, name: str):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.measurements = []
    
    def start(self):
        """Start timing measurement."""
        self.start_time = time.perf_counter()
    
    def stop(self):
        """Stop timing measurement and record result."""
        if self.start_time is None:
            raise ValueError("Must call start() before stop()")
        
        self.end_time = time.perf_counter()
        duration = self.end_time - self.start_time
        self.measurements.append(duration)
        return duration
    
    def get_statistics(self) -> Dict[str, float]:
        """Get performance statistics."""
        if not self.measurements:
            return {}
        
        return {
            "count": len(self.measurements),
            "total_time": sum(self.measurements),
            "mean": statistics.mean(self.measurements),
            "median": statistics.median(self.measurements),
            "min": min(self.measurements),
            "max": max(self.measurements),
            "std_dev": statistics.stdev(self.measurements) if len(self.measurements) > 1 else 0.0
        }


class TestPerformanceBenchmarks:
    """Performance benchmarking tests."""
    
    @pytest.fixture(scope="class")
    def large_test_data(self):
        """Create large test dataset for performance testing."""
        temp_dir = tempfile.mkdtemp()
        test_data_path = Path(temp_dir)
        
        # Create large trade dataset (10,000 trades)
        trade_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        
        for i in range(10000):
            trade_time = base_time + timedelta(seconds=i * 30)
            trade_data.append({
                'DateTime': trade_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Symbol': 'NQ' if i % 3 == 0 else 'ES',
                'TradeType': 'Buy' if i % 2 == 0 else 'Sell',
                'Quantity': 1 + (i % 5),
                'Price': 15000 + (i % 200) * 5,
                'PnL': (i % 20 - 10) * 50,
                'Commission': 2.50,
                'Account': f'ACCOUNT_{i % 10}'
            })
        
        trade_df = pd.DataFrame(trade_data)
        trade_file = test_data_path / "large_trades.csv"
        trade_df.to_csv(trade_file, index=False)
        
        # Create large market data (50,000 bars)
        market_data = []
        for i in range(50000):
            market_time = base_time + timedelta(minutes=i)
            base_price = 15000 + (i // 100) * 10
            market_data.append({
                'DateTime': market_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Symbol': 'NQ',
                'Open': base_price + (i % 10),
                'High': base_price + (i % 10) + 15,
                'Low': base_price + (i % 10) - 15,
                'Close': base_price + (i % 10) + 5,
                'Volume': 1000 + (i % 500)
            })
        
        market_df = pd.DataFrame(market_data)
        market_file = test_data_path / "large_market_data.csv"
        market_df.to_csv(market_file, index=False)
        
        yield test_data_path
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    @pytest.fixture(scope="class")
    def test_database(self):
        """Create temporary test database."""
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        # Update config to use test database
        original_db_url = config.DATABASE_URL
        config.DATABASE_URL = f"sqlite:///{temp_db.name}"
        
        # Initialize database
        from trading_platform.database.database import init_database
        init_database()
        
        yield temp_db.name
        
        # Cleanup
        config.DATABASE_URL = original_db_url
        Path(temp_db.name).unlink(missing_ok=True)
    
    @pytest.fixture
    def client(self, test_database):
        """Create test client."""
        return TestClient(app)
    
    def test_data_ingestion_performance(self, client, large_test_data, test_database):
        """Test data ingestion performance with large datasets."""
        benchmark = PerformanceBenchmark("data_ingestion")
        
        # Create test account
        account_data = {
            "name": "Performance Test Account",
            "account_type": "demo",
            "initial_balance": 100000.0,
            "currency": "USD"
        }
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Test trade data ingestion
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            ingestion_service = SierraChartIngestionService()
            trade_file = large_test_data / "large_trades.csv"
            
            benchmark.start()
            asyncio.run(ingestion_service.ingest_trade_data(str(trade_file), account_id))
            ingestion_time = benchmark.stop()
        
        # Performance assertions
        assert ingestion_time < 60.0, f"Trade ingestion took too long: {ingestion_time:.2f}s"
        
        # Verify data was ingested correctly
        response = client.get(f"/api/v1/accounts/{account_id}/trades")
        trades = response.json()["data"]
        assert len(trades) > 0
        
        # Test market data ingestion
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            market_file = large_test_data / "large_market_data.csv"
            
            benchmark.start()
            asyncio.run(ingestion_service.ingest_market_data(str(market_file)))
            market_ingestion_time = benchmark.stop()
        
        assert market_ingestion_time < 120.0, f"Market data ingestion took too long: {market_ingestion_time:.2f}s"
        
        stats = benchmark.get_statistics()
        print(f"Data Ingestion Performance: {stats}")
    
    def test_analytics_performance(self, client, large_test_data, test_database):
        """Test analytics performance with large datasets."""
        benchmark = PerformanceBenchmark("analytics")
        
        # Setup data
        account_data = {
            "name": "Analytics Performance Test",
            "account_type": "demo",
            "initial_balance": 100000.0,
            "currency": "USD"
        }
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Ingest data first
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            ingestion_service = SierraChartIngestionService()
            trade_file = large_test_data / "large_trades.csv"
            asyncio.run(ingestion_service.ingest_trade_data(str(trade_file), account_id))
        
        # Test performance analytics
        benchmark.start()
        response = client.post(f"/api/v1/analytics/account/{account_id}/performance")
        performance_time = benchmark.stop()
        
        assert response.status_code == 200
        assert performance_time < 10.0, f"Performance analytics took too long: {performance_time:.2f}s"
        
        # Test walk-forward analysis
        walkforward_params = {
            "train_period_months": 3,
            "test_period_months": 1,
            "step_size_months": 1
        }
        
        benchmark.start()
        response = client.post(
            f"/api/v1/analytics/account/{account_id}/walk-forward",
            json=walkforward_params
        )
        walkforward_time = benchmark.stop()
        
        assert response.status_code == 200
        assert walkforward_time < 30.0, f"Walk-forward analysis took too long: {walkforward_time:.2f}s"
        
        # Test Monte Carlo simulation
        monte_carlo_params = {
            "num_simulations": 1000,
            "time_horizon_days": 30,
            "confidence_level": 0.95
        }
        
        benchmark.start()
        response = client.post(
            f"/api/v1/analytics/account/{account_id}/monte-carlo",
            json=monte_carlo_params
        )
        monte_carlo_time = benchmark.stop()
        
        assert response.status_code == 200
        assert monte_carlo_time < 15.0, f"Monte Carlo simulation took too long: {monte_carlo_time:.2f}s"
        
        stats = benchmark.get_statistics()
        print(f"Analytics Performance: {stats}")
    
    def test_recommendation_engine_performance(self, client, large_test_data, test_database):
        """Test recommendation engine performance."""
        benchmark = PerformanceBenchmark("recommendations")
        
        # Setup data
        account_data = {
            "name": "Recommendation Performance Test",
            "account_type": "demo",
            "initial_balance": 100000.0,
            "currency": "USD"
        }
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Ingest data
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            ingestion_service = SierraChartIngestionService()
            trade_file = large_test_data / "large_trades.csv"
            market_file = large_test_data / "large_market_data.csv"
            
            asyncio.run(ingestion_service.ingest_trade_data(str(trade_file), account_id))
            asyncio.run(ingestion_service.ingest_market_data(str(market_file)))
        
        # Test recommendation generation
        benchmark.start()
        response = client.post(f"/api/v1/recommendations/generate/{account_id}")
        recommendation_time = benchmark.stop()
        
        assert response.status_code == 200
        assert recommendation_time < 20.0, f"Recommendation generation took too long: {recommendation_time:.2f}s"
        
        stats = benchmark.get_statistics()
        print(f"Recommendation Performance: {stats}")
    
    def test_concurrent_api_performance(self, client, large_test_data, test_database):
        """Test API performance under concurrent load."""
        
        # Setup multiple accounts with data
        account_ids = []
        for i in range(5):
            account_data = {
                "name": f"Concurrent Test Account {i}",
                "account_type": "demo",
                "initial_balance": 50000.0,
                "currency": "USD"
            }
            response = client.post("/api/v1/accounts/", json=account_data)
            account_ids.append(response.json()["data"]["account_id"])
        
        # Ingest data for each account
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            ingestion_service = SierraChartIngestionService()
            trade_file = large_test_data / "large_trades.csv"
            
            for account_id in account_ids:
                asyncio.run(ingestion_service.ingest_trade_data(str(trade_file), account_id))
        
        # Test concurrent requests
        def make_concurrent_requests(account_id: str, num_requests: int) -> List[float]:
            """Make multiple requests and measure response times."""
            response_times = []
            
            for _ in range(num_requests):
                start_time = time.perf_counter()
                response = client.get(f"/api/v1/accounts/{account_id}")
                end_time = time.perf_counter()
                
                assert response.status_code == 200
                response_times.append(end_time - start_time)
            
            return response_times
        
        # Execute concurrent requests
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for account_id in account_ids:
                future = executor.submit(make_concurrent_requests, account_id, 20)
                futures.append(future)
            
            all_response_times = []
            for future in as_completed(futures):
                response_times = future.result()
                all_response_times.extend(response_times)
        
        total_time = time.perf_counter() - start_time
        
        # Performance analysis
        total_requests = len(all_response_times)
        avg_response_time = statistics.mean(all_response_times)
        max_response_time = max(all_response_times)
        requests_per_second = total_requests / total_time
        
        print(f"Concurrent Performance Results:")
        print(f"  Total Requests: {total_requests}")
        print(f"  Total Time: {total_time:.2f}s")
        print(f"  Requests/Second: {requests_per_second:.2f}")
        print(f"  Avg Response Time: {avg_response_time:.4f}s")
        print(f"  Max Response Time: {max_response_time:.4f}s")
        
        # Performance assertions
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.4f}s"
        assert max_response_time < 5.0, f"Max response time too high: {max_response_time:.4f}s"
        assert requests_per_second > 10, f"Requests per second too low: {requests_per_second:.2f}"
    
    def test_memory_usage_performance(self, client, large_test_data, test_database):
        """Test memory usage during large operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Get baseline memory usage
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Setup account
        account_data = {
            "name": "Memory Test Account",
            "account_type": "demo",
            "initial_balance": 100000.0,
            "currency": "USD"
        }
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Ingest large dataset and monitor memory
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            ingestion_service = SierraChartIngestionService()
            trade_file = large_test_data / "large_trades.csv"
            
            # Monitor memory during ingestion
            asyncio.run(ingestion_service.ingest_trade_data(str(trade_file), account_id))
            
            peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Run analytics and monitor memory
        response = client.post(f"/api/v1/analytics/account/{account_id}/performance")
        analytics_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Memory usage analysis
        memory_increase = peak_memory - baseline_memory
        print(f"Memory Usage Analysis:")
        print(f"  Baseline Memory: {baseline_memory:.1f} MB")
        print(f"  Peak Memory: {peak_memory:.1f} MB")
        print(f"  Analytics Memory: {analytics_memory:.1f} MB")
        print(f"  Memory Increase: {memory_increase:.1f} MB")
        
        # Memory assertions (adjust thresholds based on system requirements)
        assert memory_increase < 500, f"Memory usage too high: {memory_increase:.1f} MB"
    
    def test_database_performance(self, client, large_test_data, test_database):
        """Test database query performance."""
        from trading_platform.database.database import get_database_session
        
        # Setup account with data
        account_data = {
            "name": "DB Performance Test",
            "account_type": "demo",
            "initial_balance": 100000.0,
            "currency": "USD"
        }
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Ingest data
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(large_test_data)):
            ingestion_service = SierraChartIngestionService()
            trade_file = large_test_data / "large_trades.csv"
            asyncio.run(ingestion_service.ingest_trade_data(str(trade_file), account_id))
        
        # Test database queries
        db_session = get_database_session()
        
        try:
            # Test simple select query
            start_time = time.perf_counter()
            cursor = db_session.execute("SELECT COUNT(*) FROM trades WHERE account_id = ?", (account_id,))
            trade_count = cursor.fetchone()[0]
            simple_query_time = time.perf_counter() - start_time
            
            # Test complex aggregation query
            start_time = time.perf_counter()
            cursor = db_session.execute("""
                SELECT 
                    symbol,
                    COUNT(*) as trade_count,
                    SUM(pnl) as total_pnl,
                    AVG(price) as avg_price
                FROM trades 
                WHERE account_id = ? 
                GROUP BY symbol
                ORDER BY total_pnl DESC
            """, (account_id,))
            aggregation_results = cursor.fetchall()
            aggregation_query_time = time.perf_counter() - start_time
            
            print(f"Database Performance:")
            print(f"  Trade Count: {trade_count}")
            print(f"  Simple Query Time: {simple_query_time:.4f}s")
            print(f"  Aggregation Query Time: {aggregation_query_time:.4f}s")
            
            # Performance assertions
            assert simple_query_time < 1.0, f"Simple query too slow: {simple_query_time:.4f}s"
            assert aggregation_query_time < 5.0, f"Aggregation query too slow: {aggregation_query_time:.4f}s"
            assert trade_count > 0, "No trades found in database"
            
        finally:
            db_session.close()
    
    def test_monitoring_performance_impact(self, client, test_database):
        """Test performance impact of monitoring system."""
        from trading_platform.services.monitoring.health_monitor import health_monitor
        from trading_platform.services.monitoring.metrics_collector import metrics_collector
        
        # Create test account
        account_data = {
            "name": "Monitoring Impact Test",
            "account_type": "demo",
            "initial_balance": 25000.0,
            "currency": "USD"
        }
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Measure performance without monitoring
        def make_test_requests(num_requests: int) -> float:
            start_time = time.perf_counter()
            for _ in range(num_requests):
                client.get(f"/api/v1/accounts/{account_id}")
            return time.perf_counter() - start_time
        
        # Test without monitoring
        baseline_time = make_test_requests(50)
        
        # Start monitoring
        asyncio.run(health_monitor.start_monitoring())
        
        try:
            # Test with monitoring enabled
            monitoring_time = make_test_requests(50)
            
            # Calculate overhead
            overhead = ((monitoring_time - baseline_time) / baseline_time) * 100
            
            print(f"Monitoring Performance Impact:")
            print(f"  Baseline Time: {baseline_time:.4f}s")
            print(f"  Monitoring Time: {monitoring_time:.4f}s")
            print(f"  Overhead: {overhead:.1f}%")
            
            # Monitoring should add minimal overhead
            assert overhead < 20, f"Monitoring overhead too high: {overhead:.1f}%"
            
        finally:
            asyncio.run(health_monitor.stop_monitoring())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])