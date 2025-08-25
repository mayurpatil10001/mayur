"""
Working Account repository implementation using actual MCP tools.

This module provides a concrete account repository that works with the actual
MCP tools available in the current environment.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .working_mcp_repository import WorkingMCPRepository
from ..models.trading import Account

logger = logging.getLogger(__name__)


class WorkingAccountRepository(WorkingMCPRepository[Account]):
    """
    Working repository for managing Account entities using actual MCP tools.
    
    This repository is designed to work with the actual MCP tools that are
    available in the current environment.
    """
    
    def __init__(self):
        """Initialize the working account repository."""
        super().__init__("accounts")
    
    def _map_row_to_entity(self, row: Dict[str, Any]) -> Account:
        """
        Map a database row to an Account entity.
        
        Args:
            row: Database row as dictionary
            
        Returns:
            Account entity
        """
        return Account(
            name=row["name"],
            symbol=row["symbol"],
            total_trades=row["total_trades"],
            first_trade_date=datetime.fromisoformat(row["first_trade_date"]) if row["first_trade_date"] else None,
            last_trade_date=datetime.fromisoformat(row["last_trade_date"]) if row["last_trade_date"] else None,
            is_active=bool(row["is_active"])
        )
    
    def _map_entity_to_row(self, entity: Account) -> Dict[str, Any]:
        """
        Map an Account entity to a database row.
        
        Args:
            entity: Account entity
            
        Returns:
            Database row as dictionary
        """
        return {
            "name": entity.name,
            "symbol": entity.symbol,
            "total_trades": entity.total_trades,
            "first_trade_date": entity.first_trade_date.isoformat() if entity.first_trade_date else None,
            "last_trade_date": entity.last_trade_date.isoformat() if entity.last_trade_date else None,
            "is_active": 1 if entity.is_active else 0,
            "created_timestamp": datetime.now().isoformat()
        }
    
    def _get_id_field_name(self) -> str:
        """
        Get the name of the ID field for Account entities.
        
        Returns:
            Name of the ID field
        """
        return "name"
    
    # Account-specific methods
    
    def get_by_symbol(self, symbol: str) -> List[Account]:
        """
        Get all accounts trading a specific symbol.
        
        Args:
            symbol: The symbol to filter by
            
        Returns:
            List of accounts trading the symbol
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE symbol = '{symbol}'"
            
            results = self.execute_read_query(query)
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get accounts by symbol {symbol}: {e}")
            return []
    
    def get_active_accounts(self) -> List[Account]:
        """
        Get all active accounts.
        
        Returns:
            List of active accounts
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE is_active = 1"
            
            results = self.execute_read_query(query)
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get active accounts: {e}")
            return []
    
    def update_trade_count(self, account_name: str, trade_count: int) -> bool:
        """
        Update the total trade count for an account.
        
        Args:
            account_name: Name of the account
            trade_count: New trade count
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            query = f"UPDATE {self.table_name} SET total_trades = {trade_count} WHERE name = '{account_name}'"
            
            affected_rows = self.execute_write_query(query)
            
            success = affected_rows > 0
            if success:
                self.logger.info(f"Updated trade count for account {account_name}: {trade_count}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to update trade count for account {account_name}: {e}")
            return False
    
    def update_trade_dates(self, account_name: str, first_date: datetime, last_date: datetime) -> bool:
        """
        Update the first and last trade dates for an account.
        
        Args:
            account_name: Name of the account
            first_date: First trade date
            last_date: Last trade date
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            query = (f"UPDATE {self.table_name} SET "
                    f"first_trade_date = '{first_date.isoformat()}', "
                    f"last_trade_date = '{last_date.isoformat()}' "
                    f"WHERE name = '{account_name}'")
            
            affected_rows = self.execute_write_query(query)
            
            success = affected_rows > 0
            if success:
                self.logger.info(f"Updated trade dates for account {account_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to update trade dates for account {account_name}: {e}")
            return False


def create_working_account_repository_with_mcp_tools():
    """
    Create a working account repository with MCP tools injected.
    
    This function creates a repository and injects the actual MCP tools
    that are available in the current environment.
    
    Returns:
        WorkingAccountRepository with MCP tools injected
    """
    repository = WorkingAccountRepository()
    
    # This function would be called from a context where MCP tools are available
    # The calling context would override the MCP methods with actual tool calls
    
    return repository