#!/usr/bin/env python3
"""
Unit tests for MCP repository implementations.

This module tests the repository pattern with MCP integration,
including mocked MCP tools for testing.
"""

import unittest
from unittest.mock import Mock, patch
from datetime import datetime
import sys
from pathlib import Path

# Add the trading platform to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from trading_platform.repositories.working_account_repository import WorkingAccountRepository
from trading_platform.models.trading import Account
from trading_platform.utils.validators import ValidationError


class TestWorkingAccountRepository(unittest.TestCase):
    """Test cases for WorkingAccountRepository."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.repository = WorkingAccountRepository()
        self.mock_data = [
            {
                "name": "IPS_TM_10",
                "symbol": "NQ",
                "total_trades": 150,
                "first_trade_date": "2024-01-01T09:30:00",
                "last_trade_date": "2024-12-31T16:00:00",
                "is_active": 1,
                "created_timestamp": "2024-01-01T00:00:00"
            },
            {
                "name": "IPS_TM_13",
                "symbol": "FDAX",
                "total_trades": 200,
                "first_trade_date": "2024-01-01T08:00:00",
                "last_trade_date": "2024-12-31T17:00:00",
                "is_active": 1,
                "created_timestamp": "2024-01-01T00:00:00"
            }
        ]
        
        # Mock the MCP methods
        self.repository.execute_read_query = Mock()
        self.repository.execute_write_query = Mock()
        self.repository.list_tables = Mock()
        self.repository.describe_table = Mock()
        self.repository.create_table = Mock()
    
    def test_get_all_accounts(self):
        """Test getting all accounts."""
        # Setup mock
        self.repository.execute_read_query.return_value = self.mock_data
        
        # Execute
        accounts = self.repository.get_all()
        
        # Verify
        self.assertEqual(len(accounts), 2)
        self.assertEqual(accounts[0].name, "IPS_TM_10")
        self.assertEqual(accounts[0].symbol, "NQ")
        self.assertEqual(accounts[0].total_trades, 150)
        self.assertTrue(accounts[0].is_active)
        
        self.assertEqual(accounts[1].name, "IPS_TM_13")
        self.assertEqual(accounts[1].symbol, "FDAX")
        self.assertEqual(accounts[1].total_trades, 200)
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with("SELECT * FROM accounts")
    
    def test_get_account_by_id(self):
        """Test getting account by ID."""
        # Setup mock
        self.repository.execute_read_query.return_value = [self.mock_data[0]]
        
        # Execute
        account = self.repository.get_by_id("IPS_TM_10")
        
        # Verify
        self.assertIsNotNone(account)
        self.assertEqual(account.name, "IPS_TM_10")
        self.assertEqual(account.symbol, "NQ")
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with(
            "SELECT * FROM accounts WHERE name = 'IPS_TM_10'"
        )
    
    def test_get_account_by_id_not_found(self):
        """Test getting account by ID when not found."""
        # Setup mock
        self.repository.execute_read_query.return_value = []
        
        # Execute
        account = self.repository.get_by_id("NONEXISTENT")
        
        # Verify
        self.assertIsNone(account)
    
    def test_create_account(self):
        """Test creating a new account."""
        # Setup mock
        self.repository.execute_write_query.return_value = 1
        
        # Create test account
        now = datetime.now()
        account = Account(
            name="IPS_TM_99",
            symbol="ES",
            total_trades=0,
            first_trade_date=now,
            last_trade_date=now,
            is_active=True
        )
        
        # Execute
        created_account = self.repository.create(account)
        
        # Verify
        self.assertEqual(created_account.name, "IPS_TM_99")
        self.assertEqual(created_account.symbol, "ES")
        
        # Verify write query was called
        self.repository.execute_write_query.assert_called_once()
        call_args = self.repository.execute_write_query.call_args[0][0]
        self.assertIn("INSERT INTO accounts", call_args)
        self.assertIn("IPS_TM_99", call_args)
        self.assertIn("ES", call_args)
    
    def test_update_account(self):
        """Test updating an existing account."""
        # Setup mock
        self.repository.execute_write_query.return_value = 1
        
        # Create test account
        now = datetime.now()
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=200,
            first_trade_date=now,
            last_trade_date=now,
            is_active=True
        )
        
        # Execute
        updated_account = self.repository.update(account)
        
        # Verify
        self.assertEqual(updated_account.name, "IPS_TM_10")
        self.assertEqual(updated_account.total_trades, 200)
        
        # Verify write query was called
        self.repository.execute_write_query.assert_called_once()
        call_args = self.repository.execute_write_query.call_args[0][0]
        self.assertIn("UPDATE accounts SET", call_args)
        self.assertIn("WHERE name = 'IPS_TM_10'", call_args)
    
    def test_delete_account(self):
        """Test deleting an account."""
        # Setup mock
        self.repository.execute_write_query.return_value = 1
        
        # Execute
        result = self.repository.delete("IPS_TM_10")
        
        # Verify
        self.assertTrue(result)
        
        # Verify write query was called
        self.repository.execute_write_query.assert_called_once_with(
            "DELETE FROM accounts WHERE name = 'IPS_TM_10'"
        )
    
    def test_delete_account_not_found(self):
        """Test deleting an account that doesn't exist."""
        # Setup mock
        self.repository.execute_write_query.return_value = 0
        
        # Execute
        result = self.repository.delete("NONEXISTENT")
        
        # Verify
        self.assertFalse(result)
    
    def test_exists_account(self):
        """Test checking if account exists."""
        # Setup mock
        self.repository.execute_read_query.return_value = [{"1": 1}]
        
        # Execute
        exists = self.repository.exists("IPS_TM_10")
        
        # Verify
        self.assertTrue(exists)
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with(
            "SELECT 1 FROM accounts WHERE name = 'IPS_TM_10' LIMIT 1"
        )
    
    def test_exists_account_not_found(self):
        """Test checking if account exists when it doesn't."""
        # Setup mock
        self.repository.execute_read_query.return_value = []
        
        # Execute
        exists = self.repository.exists("NONEXISTENT")
        
        # Verify
        self.assertFalse(exists)
    
    def test_count_accounts(self):
        """Test counting accounts."""
        # Setup mock
        self.repository.execute_read_query.return_value = [{"count": 5}]
        
        # Execute
        count = self.repository.count()
        
        # Verify
        self.assertEqual(count, 5)
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with(
            "SELECT COUNT(*) as count FROM accounts"
        )
    
    def test_get_by_symbol(self):
        """Test getting accounts by symbol."""
        # Setup mock
        nq_accounts = [acc for acc in self.mock_data if acc["symbol"] == "NQ"]
        self.repository.execute_read_query.return_value = nq_accounts
        
        # Execute
        accounts = self.repository.get_by_symbol("NQ")
        
        # Verify
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0].symbol, "NQ")
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with(
            "SELECT * FROM accounts WHERE symbol = 'NQ'"
        )
    
    def test_get_active_accounts(self):
        """Test getting active accounts."""
        # Setup mock
        active_accounts = [acc for acc in self.mock_data if acc["is_active"] == 1]
        self.repository.execute_read_query.return_value = active_accounts
        
        # Execute
        accounts = self.repository.get_active_accounts()
        
        # Verify
        self.assertEqual(len(accounts), 2)
        for account in accounts:
            self.assertTrue(account.is_active)
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with(
            "SELECT * FROM accounts WHERE is_active = 1"
        )
    
    def test_update_trade_count(self):
        """Test updating trade count."""
        # Setup mock
        self.repository.execute_write_query.return_value = 1
        
        # Execute
        result = self.repository.update_trade_count("IPS_TM_10", 250)
        
        # Verify
        self.assertTrue(result)
        
        # Verify query was called
        self.repository.execute_write_query.assert_called_once_with(
            "UPDATE accounts SET total_trades = 250 WHERE name = 'IPS_TM_10'"
        )
    
    def test_update_trade_dates(self):
        """Test updating trade dates."""
        # Setup mock
        self.repository.execute_write_query.return_value = 1
        
        # Test dates
        first_date = datetime(2024, 1, 1, 9, 30)
        last_date = datetime(2024, 12, 31, 16, 0)
        
        # Execute
        result = self.repository.update_trade_dates("IPS_TM_10", first_date, last_date)
        
        # Verify
        self.assertTrue(result)
        
        # Verify query was called
        self.repository.execute_write_query.assert_called_once()
        call_args = self.repository.execute_write_query.call_args[0][0]
        self.assertIn("UPDATE accounts SET", call_args)
        self.assertIn("first_trade_date =", call_args)
        self.assertIn("last_trade_date =", call_args)
        self.assertIn("WHERE name = 'IPS_TM_10'", call_args)
    
    def test_health_check(self):
        """Test repository health check."""
        # Setup mock
        self.repository.execute_read_query.return_value = [{"test": 1}]
        
        # Execute
        health = self.repository.health_check()
        
        # Verify
        self.assertTrue(health)
        
        # Verify query was called
        self.repository.execute_read_query.assert_called_once_with("SELECT 1 as test")
    
    def test_health_check_failure(self):
        """Test repository health check failure."""
        # Setup mock to raise exception
        self.repository.execute_read_query.side_effect = Exception("Connection failed")
        
        # Execute
        health = self.repository.health_check()
        
        # Verify
        self.assertFalse(health)
    
    def test_get_table_info(self):
        """Test getting table info."""
        # Setup mocks
        self.repository.list_tables.return_value = ["accounts", "trades"]
        self.repository.execute_read_query.return_value = [{"count": 3}]
        
        # Execute
        table_info = self.repository.get_table_info()
        
        # Verify
        self.assertEqual(table_info["table_name"], "accounts")
        self.assertTrue(table_info["exists"])
        self.assertEqual(table_info["count"], 3)
    
    def test_map_row_to_entity(self):
        """Test mapping database row to Account entity."""
        # Test data
        row = self.mock_data[0]
        
        # Execute
        account = self.repository._map_row_to_entity(row)
        
        # Verify
        self.assertEqual(account.name, "IPS_TM_10")
        self.assertEqual(account.symbol, "NQ")
        self.assertEqual(account.total_trades, 150)
        self.assertTrue(account.is_active)
        self.assertIsInstance(account.first_trade_date, datetime)
        self.assertIsInstance(account.last_trade_date, datetime)
    
    def test_map_entity_to_row(self):
        """Test mapping Account entity to database row."""
        # Create test account
        now = datetime.now()
        account = Account(
            name="IPS_TM_99",
            symbol="ES",
            total_trades=100,
            first_trade_date=now,
            last_trade_date=now,
            is_active=True
        )
        
        # Execute
        row = self.repository._map_entity_to_row(account)
        
        # Verify
        self.assertEqual(row["name"], "IPS_TM_99")
        self.assertEqual(row["symbol"], "ES")
        self.assertEqual(row["total_trades"], 100)
        self.assertEqual(row["is_active"], 1)
        self.assertIn("created_timestamp", row)
    
    def test_get_id_field_name(self):
        """Test getting ID field name."""
        id_field = self.repository._get_id_field_name()
        self.assertEqual(id_field, "name")


class TestAccountValidation(unittest.TestCase):
    """Test cases for Account model validation."""
    
    def test_valid_account_creation(self):
        """Test creating a valid account."""
        now = datetime.now()
        account = Account(
            name="IPS_TM_10",
            symbol="NQ",
            total_trades=100,
            first_trade_date=now,
            last_trade_date=now,
            is_active=True
        )
        
        self.assertEqual(account.name, "IPS_TM_10")
        self.assertEqual(account.symbol, "NQ")
        self.assertEqual(account.total_trades, 100)
        self.assertTrue(account.is_active)
    
    def test_invalid_account_name(self):
        """Test creating account with invalid name."""
        now = datetime.now()
        
        with self.assertRaises(ValidationError):
            Account(
                name="INVALID_NAME",
                symbol="NQ",
                total_trades=100,
                first_trade_date=now,
                last_trade_date=now,
                is_active=True
            )
    
    def test_invalid_trade_dates(self):
        """Test creating account with invalid trade dates."""
        first_date = datetime(2024, 12, 31)
        last_date = datetime(2024, 1, 1)  # Before first date
        
        with self.assertRaises(ValidationError):
            Account(
                name="IPS_TM_10",
                symbol="NQ",
                total_trades=100,
                first_trade_date=first_date,
                last_trade_date=last_date,
                is_active=True
            )
    
    def test_negative_trade_count(self):
        """Test creating account with negative trade count."""
        now = datetime.now()
        
        with self.assertRaises(ValidationError):
            Account(
                name="IPS_TM_10",
                symbol="NQ",
                total_trades=-10,
                first_trade_date=now,
                last_trade_date=now,
                is_active=True
            )


if __name__ == "__main__":
    unittest.main()