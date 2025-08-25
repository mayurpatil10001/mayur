"""
End-to-end integration tests for the trading optimization platform.

Tests the complete system functionality including data ingestion,
analysis, recommendations, and monitoring.

Requirements: 8.2, 8.4
"""

import pytest
import asyncio
import tempfile
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from trading_platform.api.main import app
from trading_platform.config import config
from trading_platform.database.database import get_database_session
from trading_platform.services.data_ingestion import SierraChartIngestionService
from trading_platform.services.analytics import AnalyticsService
from trading_platform.services.recommendations import RecommendationEngine
from trading_platform.services.monitoring.health_monitor import health_monitor
from trading_platform.services.monitoring.metrics_collector import metrics_collector
from trading_platform.services.monitoring.alert_manager import get_alert_manager


class TestEndToEndIntegration:
    """End-to-end integration tests."""
    
    @pytest.fixture(scope="class")
    def test_data_dir(self):
        """Create temporary directory with test data."""
        temp_dir = tempfile.mkdtemp()
        test_data_path = Path(temp_dir)
        
        # Create sample SierraChart data files
        self._create_sample_data_files(test_data_path)
        
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
    
    def _create_sample_data_files(self, data_path: Path) -> None:
        """Create sample data files for testing."""
        # Create sample trade data
        trade_data = []
        base_time = datetime(2024, 1, 1, 9, 30, 0)
        
        for i in range(100):
            trade_time = base_time + timedelta(minutes=i * 5)
            trade_data.append({
                'DateTime': trade_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Symbol': 'NQ',
                'TradeType': 'Buy' if i % 2 == 0 else 'Sell',
                'Quantity': 1,
                'Price': 15000 + (i % 20) * 10,
                'PnL': (i % 10 - 5) * 100,
                'Commission': 2.50,
                'Account': 'TEST_ACCOUNT'
            })
        
        trade_df = pd.DataFrame(trade_data)
        trade_file = data_path / "trades.csv"
        trade_df.to_csv(trade_file, index=False)
        
        # Create sample market data
        market_data = []
        for i in range(1000):
            market_time = base_time + timedelta(minutes=i)
            market_data.append({
                'DateTime': market_time.strftime('%Y-%m-%d %H:%M:%S'),
                'Symbol': 'NQ',
                'Open': 15000 + (i % 50),
                'High': 15000 + (i % 50) + 10,
                'Low': 15000 + (i % 50) - 10,
                'Close': 15000 + (i % 50) + 5,
                'Volume': 1000 + (i % 100)
            })
        
        market_df = pd.DataFrame(market_data)
        market_file = data_path / "market_data.csv"
        market_df.to_csv(market_file, index=False)
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self, client, test_data_dir, test_database):
        """Test complete workflow from data ingestion to recommendations."""
        
        # Step 1: Create account
        account_data = {
            "name": "Test Account",
            "account_type": "demo",
            "initial_balance": 100000.0,
            "currency": "USD"
        }
        
        response = client.post("/api/v1/accounts/", json=account_data)
        assert response.status_code == 200
        account = response.json()["data"]
        account_id = account["account_id"]
        
        # Step 2: Ingest data
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(test_data_dir)):
            ingestion_service = SierraChartIngestionService()
            
            # Ingest trade data
            trade_file = test_data_dir / "trades.csv"
            await ingestion_service.ingest_trade_data(str(trade_file), account_id)
            
            # Ingest market data
            market_file = test_data_dir / "market_data.csv"
            await ingestion_service.ingest_market_data(str(market_file))
        
        # Step 3: Verify data ingestion via API
        response = client.get(f"/api/v1/accounts/{account_id}/trades")
        assert response.status_code == 200
        trades = response.json()["data"]
        assert len(trades) > 0
        
        # Step 4: Run analytics
        response = client.post(f"/api/v1/analytics/account/{account_id}/performance")
        assert response.status_code == 200
        performance = response.json()["data"]
        
        assert "total_trades" in performance
        assert "total_pnl" in performance
        assert "win_rate" in performance
        assert performance["total_trades"] > 0
        
        # Step 5: Run Monte Carlo simulation
        monte_carlo_params = {
            "num_simulations": 100,
            "time_horizon_days": 30,
            "confidence_level": 0.95
        }
        
        response = client.post(
            f"/api/v1/analytics/account/{account_id}/monte-carlo",
            json=monte_carlo_params
        )
        assert response.status_code == 200
        monte_carlo = response.json()["data"]
        
        assert "simulations" in monte_carlo
        assert "statistics" in monte_carlo
        assert len(monte_carlo["simulations"]) == 100
        
        # Step 6: Generate recommendations
        response = client.post(f"/api/v1/recommendations/generate/{account_id}")
        assert response.status_code == 200
        recommendations = response.json()["data"]
        
        assert isinstance(recommendations, list)
        if recommendations:  # May be empty if no patterns found
            for rec in recommendations:
                assert "recommendation_type" in rec
                assert "confidence" in rec
                assert "reasoning" in rec
        
        # Step 7: Test monitoring endpoints
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        health = response.json()["data"]
        assert health["status"] in ["healthy", "unhealthy"]
        
        # Step 8: Test metrics collection
        response = client.get("/api/v1/health/metrics")
        assert response.status_code == 200
        metrics = response.json()["data"]
        assert "metrics_summary" in metrics
        
        # Step 9: Test alert system
        response = client.get("/api/v1/health/alerts")
        assert response.status_code == 200
        alert_summary = response.json()["data"]
        assert "monitoring_status" in alert_summary
        assert "total_rules" in alert_summary
    
    @pytest.mark.asyncio
    async def test_data_consistency(self, client, test_data_dir, test_database):
        """Test data consistency across different API endpoints."""
        
        # Create account
        account_data = {
            "name": "Consistency Test Account",
            "account_type": "live",
            "initial_balance": 50000.0,
            "currency": "USD"
        }
        
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Ingest data
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(test_data_dir)):
            ingestion_service = SierraChartIngestionService()
            trade_file = test_data_dir / "trades.csv"
            await ingestion_service.ingest_trade_data(str(trade_file), account_id)
        
        # Get trades from different endpoints
        response1 = client.get(f"/api/v1/accounts/{account_id}/trades")
        trades_from_account = response1.json()["data"]
        
        response2 = client.get("/api/v1/trades/", params={"account_id": account_id})
        trades_from_trades_endpoint = response2.json()["data"]
        
        # Verify consistency
        assert len(trades_from_account) == len(trades_from_trades_endpoint)
        
        # Verify trade IDs match
        account_trade_ids = {trade["trade_id"] for trade in trades_from_account}
        endpoint_trade_ids = {trade["trade_id"] for trade in trades_from_trades_endpoint}
        assert account_trade_ids == endpoint_trade_ids
        
        # Get analytics and verify they match the trade data
        response = client.post(f"/api/v1/analytics/account/{account_id}/performance")
        performance = response.json()["data"]
        
        # Count trades manually vs analytics
        manual_trade_count = len(trades_from_account)
        analytics_trade_count = performance["total_trades"]
        assert manual_trade_count == analytics_trade_count
    
    @pytest.mark.asyncio 
    async def test_error_handling(self, client, test_database):
        """Test error handling across the system."""
        
        # Test with non-existent account
        response = client.get("/api/v1/accounts/99999/trades")
        assert response.status_code == 404
        
        # Test analytics with non-existent account
        response = client.post("/api/v1/analytics/account/99999/performance")
        assert response.status_code == 404
        
        # Test recommendations with non-existent account
        response = client.post("/api/v1/recommendations/generate/99999")
        assert response.status_code == 404
        
        # Test invalid data ingestion
        response = client.post("/api/v1/data/ingest", json={
            "data_type": "trades",
            "file_path": "/nonexistent/file.csv",
            "account_id": "invalid"
        })
        assert response.status_code in [400, 404, 422]
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, client, test_data_dir, test_database):
        """Test system performance under simulated load."""
        
        # Create multiple accounts
        account_ids = []
        for i in range(5):
            account_data = {
                "name": f"Load Test Account {i}",
                "account_type": "demo",
                "initial_balance": 10000.0,
                "currency": "USD"
            }
            response = client.post("/api/v1/accounts/", json=account_data)
            account_ids.append(response.json()["data"]["account_id"])
        
        # Ingest data for each account
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(test_data_dir)):
            ingestion_service = SierraChartIngestionService()
            trade_file = test_data_dir / "trades.csv"
            
            start_time = datetime.now()
            for account_id in account_ids:
                await ingestion_service.ingest_trade_data(str(trade_file), account_id)
            ingestion_time = (datetime.now() - start_time).total_seconds()
        
        # Test concurrent analytics requests
        import asyncio
        
        async def run_analytics(account_id):
            response = client.post(f"/api/v1/analytics/account/{account_id}/performance")
            return response.status_code == 200
        
        start_time = datetime.now()
        tasks = [run_analytics(account_id) for account_id in account_ids]
        results = await asyncio.gather(*tasks)
        analytics_time = (datetime.now() - start_time).total_seconds()
        
        # Verify all requests succeeded
        assert all(results)
        
        # Performance assertions (adjust thresholds as needed)
        assert ingestion_time < 30.0, f"Data ingestion took too long: {ingestion_time}s"
        assert analytics_time < 10.0, f"Analytics took too long: {analytics_time}s"
    
    @pytest.mark.asyncio
    async def test_monitoring_integration(self, client, test_database):
        """Test integration with monitoring and alerting system."""
        
        # Start health monitoring
        await health_monitor.start_monitoring()
        
        # Start alert monitoring
        alert_manager = get_alert_manager(health_monitor, metrics_collector)
        await alert_manager.start_monitoring()
        
        try:
            # Generate some activity to create metrics
            account_data = {
                "name": "Monitoring Test Account",
                "account_type": "demo",
                "initial_balance": 25000.0,
                "currency": "USD"
            }
            response = client.post("/api/v1/accounts/", json=account_data)
            account_id = response.json()["data"]["account_id"]
            
            # Make several API calls to generate metrics
            for _ in range(10):
                client.get(f"/api/v1/accounts/{account_id}")
                client.get("/api/v1/health")
                client.get("/api/v1/health/metrics")
            
            # Wait a moment for metrics to be collected
            await asyncio.sleep(2)
            
            # Check that metrics were collected
            response = client.get("/api/v1/health/metrics")
            assert response.status_code == 200
            metrics_data = response.json()["data"]
            
            assert "metrics_summary" in metrics_data
            assert "recent_metrics" in metrics_data
            
            # Check endpoint metrics
            response = client.get("/api/v1/health/endpoints")
            assert response.status_code == 200
            endpoint_metrics = response.json()["data"]
            
            assert "endpoints" in endpoint_metrics
            
            # Check that we have metrics for the endpoints we called
            endpoints = endpoint_metrics["endpoints"]
            assert any("accounts" in endpoint for endpoint in endpoints.keys())
            assert any("health" in endpoint for endpoint in endpoints.keys())
            
            # Check alert system
            response = client.get("/api/v1/health/alerts")
            assert response.status_code == 200
            alert_summary = response.json()["data"]
            
            assert alert_summary["monitoring_status"] == "running"
            assert alert_summary["total_rules"] > 0
            
        finally:
            # Stop monitoring
            await health_monitor.stop_monitoring()
            await alert_manager.stop_monitoring()
    
    @pytest.mark.asyncio
    async def test_database_transactions(self, client, test_data_dir, test_database):
        """Test database transaction integrity."""
        
        # Create account
        account_data = {
            "name": "Transaction Test Account",
            "account_type": "demo", 
            "initial_balance": 15000.0,
            "currency": "USD"
        }
        
        response = client.post("/api/v1/accounts/", json=account_data)
        account_id = response.json()["data"]["account_id"]
        
        # Get initial trade count
        response = client.get(f"/api/v1/accounts/{account_id}/trades")
        initial_trade_count = len(response.json()["data"])
        
        # Ingest data
        with patch.object(config, 'SIERRA_CHART_DATA_PATH', str(test_data_dir)):
            ingestion_service = SierraChartIngestionService()
            trade_file = test_data_dir / "trades.csv"
            await ingestion_service.ingest_trade_data(str(trade_file), account_id)
        
        # Verify trades were added
        response = client.get(f"/api/v1/accounts/{account_id}/trades")
        final_trade_count = len(response.json()["data"])
        assert final_trade_count > initial_trade_count
        
        # Verify data integrity by checking database directly
        db_session = get_database_session()
        try:
            cursor = db_session.execute(
                "SELECT COUNT(*) FROM trades WHERE account_id = ?",
                (account_id,)
            )
            db_trade_count = cursor.fetchone()[0]
            assert db_trade_count == final_trade_count
            
            # Check that all trades have required fields
            cursor = db_session.execute(
                "SELECT * FROM trades WHERE account_id = ? AND (symbol IS NULL OR quantity IS NULL OR price IS NULL)",
                (account_id,)
            )
            invalid_trades = cursor.fetchall()
            assert len(invalid_trades) == 0, "Found trades with missing required fields"
            
        finally:
            db_session.close()
    
    @pytest.mark.asyncio
    async def test_api_authentication_flow(self, client, test_database):
        """Test API authentication and authorization."""
        
        # Test accessing protected endpoint without authentication
        response = client.get("/api/v1/analytics/account/1/performance")
        # Note: Actual auth implementation may vary, adjust expected status code
        assert response.status_code in [401, 403, 422], "Expected authentication error"
        
        # Test health endpoint (should be accessible)
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_data_validation(self, client, test_database):
        """Test data validation across endpoints."""
        
        # Test invalid account creation
        invalid_account_data = {
            "name": "",  # Empty name
            "account_type": "invalid_type",
            "initial_balance": -1000.0,  # Negative balance
            "currency": "INVALID"
        }
        
        response = client.post("/api/v1/accounts/", json=invalid_account_data)
        assert response.status_code == 422, "Expected validation error"
        
        # Test valid account creation
        valid_account_data = {
            "name": "Valid Account",
            "account_type": "demo",
            "initial_balance": 5000.0,
            "currency": "USD"
        }
        
        response = client.post("/api/v1/accounts/", json=valid_account_data)
        assert response.status_code == 200
        
        # Test invalid data ingestion
        invalid_ingestion_data = {
            "data_type": "invalid_type",
            "file_path": "",
            "account_id": "not_a_number"
        }
        
        response = client.post("/api/v1/data/ingest", json=invalid_ingestion_data)
        assert response.status_code in [400, 422], "Expected validation error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])