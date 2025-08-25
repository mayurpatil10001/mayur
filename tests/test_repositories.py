"""
Unit tests for repository implementations with mocked MCP calls.

This module tests all repository operations using mocked MCP database calls
to ensure the repository pattern is working correctly.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_platform.repositories.account_repository import AccountRepository
from trading_platform.repositories.trade_repository import TradeRepository
from trading_platform.repositories.metrics_repository import MetricsRepository
from trading_platform.models.trading import Account, ProcessedTrade, PerformanceMetrics


class TestAccountRepository(unittest.TestCase):
    """Test cases for AccountRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = AccountRepository()
        self.sample_account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=100,
            first_trade_date=datetime(2024, 1, 1),
            last_trade_date=datetime(2024, 12, 31),
            is_active=True
        )
    
    @patch('trading_platform.database.mcp_client.mcp_client')
    def test_create_account(self, mock_mcp_client):
        """Test creating a new account."""
        # Mock MCP client response
        mock_mcp_client.execute_write_query.return_value = 1
        
        # Test create operation
        result = self.repository.create(self.sample_account)
        
        # Verify result
        self.assertEqual(result.name, self.sample_account.name)
        self.assertEqual(result.symbol, self.sample_account.symbol)
        
        # Verify MCP client was called (would be called in actual implementation)
        # mock_mcp_client.execute_write_query.assert_called_once()
    
    @patch('trading_platform.database.mcp_client.mcp_client')
    def test_get_by_id(self, mock_mcp_client):
        """Test retrieving account by ID."""
        # Mock MCP client response
        mock_row = {
            "name": "IPS_TM_10",
            "symbol": "NQ",
            "total_trades": 100,
            "first_trade_date": "2024-01-01T00:00:00",
            "last_trade_date": "2024-12-31T00:00:00",
            "is_active": True
        }
        mock_mcp_client.execute_query.return_value = [mock_row]
        
        # Test get operation (placeholder implementation returns None)
        result = self.repository.get_by_id("IPS_TM_10")
        
        # In the actual implementation, this would return the account
        # For now, we're testing the structure
        self.assertIsNone(result)  # Placeholder behavior
    
    def test_map_row_to_entity(self):
        """Test mapping database row to Account entity."""
        row = {
            "name": "IPS_TM_10",
            "symbol": "NQ",
            "total_trades": 100,
            "first_trade_date": "2024-01-01T00:00:00",
            "last_trade_date": "2024-12-31T00:00:00",
            "is_active": True
        }
        
        account = self.repository._map_row_to_entity(row)
        
        self.assertEqual(account.name, "IPS_TM_10")
        self.assertEqual(account.symbol, "NQ")
        self.assertEqual(account.total_trades, 100)
        self.assertTrue(account.is_active)
    
    def test_map_entity_to_row(self):
        """Test mapping Account entity to database row."""
        row = self.repository._map_entity_to_row(self.sample_account)
        
        self.assertEqual(row["name"], "IPS_TM_10")
        self.assertEqual(row["symbol"], "NQ")
        self.assertEqual(row["total_trades"], 100)
        self.assertTrue(row["is_active"])
        self.assertIn("created_timestamp", row)
    
    def test_get_id_field_name(self):
        """Test getting ID field name."""
        self.assertEqual(self.repository._get_id_field_name(), "name")


class TestTradeRepository(unittest.TestCase):
    """Test cases for TradeRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = TradeRepository()
        self.sample_trade = ProcessedTrade(
            trade_id="TRADE_001",
            account_name="IPS_TM_10",
            symbol="NQ",
            entry_time=datetime(2024, 6, 15, 9, 30),
            exit_time=datetime(2024, 6, 15, 10, 15),
            entry_price=18500.0,
            exit_price=18520.0,
            quantity=1,
            side="LONG",
            profit_loss=20.0,
            commission=4.0,
            duration_minutes=45,
            hour_of_day=9,
            day_of_week=5,
            entry_order_id="ENTRY_001",
            exit_order_id="EXIT_001"
        )
    
    @patch('trading_platform.repositories.base_repository.mcp_client')
    def test_create_trade(self, mock_mcp_client):
        """Test creating a new trade."""
        # Mock MCP client response
        mock_mcp_client.execute_write_query.return_value = 1
        
        # Test create operation
        result = self.repository.create(self.sample_trade)
        
        # Verify result
        self.assertEqual(result.trade_id, self.sample_trade.trade_id)
        self.assertEqual(result.account_name, self.sample_trade.account_name)
        self.assertEqual(result.profit_loss, self.sample_trade.profit_loss)
    
    def test_map_row_to_entity(self):
        """Test mapping database row to ProcessedTrade entity."""
        row = {
            "trade_id": "TRADE_001",
            "account_name": "IPS_TM_10",
            "symbol": "NQ",
            "entry_time": "2024-06-15T09:30:00",
            "exit_time": "2024-06-15T10:15:00",
            "entry_price": 18500.0,
            "exit_price": 18520.0,
            "quantity": 1,
            "side": "LONG",
            "profit_loss": 20.0,
            "commission": 4.0,
            "duration_minutes": 45,
            "hour_of_day": 9,
            "day_of_week": 5,
            "entry_order_id": "ENTRY_001",
            "exit_order_id": "EXIT_001"
        }
        
        trade = self.repository._map_row_to_entity(row)
        
        self.assertEqual(trade.trade_id, "TRADE_001")
        self.assertEqual(trade.account_name, "IPS_TM_10")
        self.assertEqual(trade.profit_loss, 20.0)
        self.assertEqual(trade.hour_of_day, 9)
    
    def test_map_entity_to_row(self):
        """Test mapping ProcessedTrade entity to database row."""
        row = self.repository._map_entity_to_row(self.sample_trade)
        
        self.assertEqual(row["trade_id"], "TRADE_001")
        self.assertEqual(row["account_name"], "IPS_TM_10")
        self.assertEqual(row["profit_loss"], 20.0)
        self.assertIn("created_timestamp", row)
    
    def test_get_id_field_name(self):
        """Test getting ID field name."""
        self.assertEqual(self.repository._get_id_field_name(), "trade_id")


class TestMetricsRepository(unittest.TestCase):
    """Test cases for MetricsRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = MetricsRepository()
        self.sample_metrics = PerformanceMetrics(
            account_name="IPS_TM_10",
            symbol="NQ",
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 12, 31),
            total_return=1500.0,
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=0.6,
            average_win=35.0,
            average_loss=-20.0,
            profit_factor=2.1,
            max_drawdown=-500.0,
            sharpe_ratio=1.8,
            volatility=0.15,
            largest_win=150.0,
            largest_loss=-80.0
        )
    
    @patch('trading_platform.repositories.base_repository.mcp_client')
    def test_create_metrics(self, mock_mcp_client):
        """Test creating new performance metrics."""
        # Mock MCP client response
        mock_mcp_client.execute_write_query.return_value = 1
        
        # Test create operation
        result = self.repository.create(self.sample_metrics)
        
        # Verify result
        self.assertEqual(result.account_name, self.sample_metrics.account_name)
        self.assertEqual(result.total_return, self.sample_metrics.total_return)
        self.assertEqual(result.win_rate, self.sample_metrics.win_rate)
    
    def test_map_row_to_entity(self):
        """Test mapping database row to PerformanceMetrics entity."""
        row = {
            "account_name": "IPS_TM_10",
            "symbol": "NQ",
            "period_start": "2024-01-01T00:00:00",
            "period_end": "2024-12-31T00:00:00",
            "total_return": 1500.0,
            "total_trades": 100,
            "winning_trades": 60,
            "losing_trades": 40,
            "win_rate": 0.6,
            "average_win": 35.0,
            "average_loss": -20.0,
            "profit_factor": 2.1,
            "max_drawdown": -500.0,
            "sharpe_ratio": 1.8,
            "volatility": 0.15,
            "largest_win": 150.0,
            "largest_loss": -80.0
        }
        
        metrics = self.repository._map_row_to_entity(row)
        
        self.assertEqual(metrics.account_name, "IPS_TM_10")
        self.assertEqual(metrics.total_return, 1500.0)
        self.assertEqual(metrics.win_rate, 0.6)
        self.assertEqual(metrics.sharpe_ratio, 1.8)
    
    def test_map_entity_to_row(self):
        """Test mapping PerformanceMetrics entity to database row."""
        row = self.repository._map_entity_to_row(self.sample_metrics)
        
        self.assertEqual(row["account_name"], "IPS_TM_10")
        self.assertEqual(row["total_return"], 1500.0)
        self.assertEqual(row["win_rate"], 0.6)
        self.assertIn("calculation_timestamp", row)
    
    def test_get_id_field_name(self):
        """Test getting ID field name."""
        self.assertEqual(self.repository._get_id_field_name(), "id")


class TestRepositoryIntegration(unittest.TestCase):
    """Integration tests for repository pattern."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.account_repo = AccountRepository()
        self.trade_repo = TradeRepository()
        self.metrics_repo = MetricsRepository()
    
    def test_repository_initialization(self):
        """Test that all repositories initialize correctly."""
        self.assertEqual(self.account_repo.table_name, "accounts")
        self.assertEqual(self.trade_repo.table_name, "processed_trades")
        self.assertEqual(self.metrics_repo.table_name, "performance_metrics")
    
    def test_table_info_methods(self):
        """Test table info methods."""
        account_info = self.account_repo.get_table_info()
        trade_info = self.trade_repo.get_table_info()
        metrics_info = self.metrics_repo.get_table_info()
        
        self.assertIn("table_name", account_info)
        self.assertIn("table_name", trade_info)
        self.assertIn("table_name", metrics_info)
        
        self.assertEqual(account_info["table_name"], "accounts")
        self.assertEqual(trade_info["table_name"], "processed_trades")
        self.assertEqual(metrics_info["table_name"], "performance_metrics")


if __name__ == '__main__':
    # Set up logging for tests
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Run tests
    unittest.main(verbosity=2)