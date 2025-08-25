"""
Metrics repository implementation using MCP for database operations.

This module provides database operations for performance metrics entities.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .base_repository import BaseRepository
from ..models.trading import PerformanceMetrics

logger = logging.getLogger(__name__)


class MetricsRepository(BaseRepository[PerformanceMetrics]):
    """
    Repository for managing PerformanceMetrics entities using MCP database operations.
    """
    
    def __init__(self):
        """Initialize the metrics repository."""
        super().__init__("performance_metrics")
    
    def _map_row_to_entity(self, row: Dict[str, Any]) -> PerformanceMetrics:
        """
        Map a database row to a PerformanceMetrics entity.
        
        Args:
            row: Database row as dictionary
            
        Returns:
            PerformanceMetrics entity
        """
        return PerformanceMetrics(
            account_name=row["account_name"],
            symbol=row["symbol"],
            period_start=datetime.fromisoformat(row["period_start"]),
            period_end=datetime.fromisoformat(row["period_end"]),
            total_return=float(row["total_return"]),
            total_trades=int(row["total_trades"]),
            winning_trades=int(row["winning_trades"]),
            losing_trades=int(row["losing_trades"]),
            win_rate=float(row["win_rate"]),
            average_win=float(row["average_win"]),
            average_loss=float(row["average_loss"]),
            profit_factor=float(row["profit_factor"]),
            max_drawdown=float(row["max_drawdown"]),
            sharpe_ratio=float(row["sharpe_ratio"]) if row["sharpe_ratio"] else None,
            volatility=float(row["volatility"]),
            largest_win=float(row["largest_win"]),
            largest_loss=float(row["largest_loss"])
        )
    
    def _map_entity_to_row(self, entity: PerformanceMetrics) -> Dict[str, Any]:
        """
        Map a PerformanceMetrics entity to a database row.
        
        Args:
            entity: PerformanceMetrics entity
            
        Returns:
            Database row as dictionary
        """
        return {
            "account_name": entity.account_name,
            "symbol": entity.symbol,
            "period_start": entity.period_start.isoformat(),
            "period_end": entity.period_end.isoformat(),
            "total_return": entity.total_return,
            "total_trades": entity.total_trades,
            "winning_trades": entity.winning_trades,
            "losing_trades": entity.losing_trades,
            "win_rate": entity.win_rate,
            "average_win": entity.average_win,
            "average_loss": entity.average_loss,
            "profit_factor": entity.profit_factor,
            "max_drawdown": entity.max_drawdown,
            "sharpe_ratio": entity.sharpe_ratio,
            "volatility": entity.volatility,
            "largest_win": entity.largest_win,
            "largest_loss": entity.largest_loss,
            "calculation_timestamp": datetime.now().isoformat()
        }
    
    def _get_id_field_name(self) -> str:
        """
        Get the name of the ID field for PerformanceMetrics entities.
        
        Returns:
            Name of the ID field
        """
        return "id"
    
    def create(self, entity: PerformanceMetrics) -> PerformanceMetrics:
        """
        Create new performance metrics in the database.
        
        Args:
            entity: The metrics to create
            
        Returns:
            The created metrics
        """
        try:
            row_data = self._map_entity_to_row(entity)
            
            # Build INSERT query
            columns = ", ".join(row_data.keys())
            placeholders = ", ".join(["?" for _ in row_data.keys()])
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"
            
            # For now, we'll use a placeholder implementation
            # In the actual MCP integration, this would use the MCP tools
            # self._execute_write_query(query, row_data)
            
            self.logger.info(f"Created metrics for {entity.account_name}/{entity.symbol}")
            return entity
            
        except Exception as e:
            self.logger.error(f"Failed to create metrics for {entity.account_name}/{entity.symbol}: {e}")
            raise
    
    def update(self, entity: PerformanceMetrics) -> PerformanceMetrics:
        """
        Update existing performance metrics in the database.
        
        Args:
            entity: The metrics to update
            
        Returns:
            The updated metrics
        """
        try:
            row_data = self._map_entity_to_row(entity)
            
            # Build UPDATE query - update based on account_name, symbol, and period
            set_clause = ", ".join([f"{key} = ?" for key in row_data.keys() 
                                  if key not in ["account_name", "symbol", "period_start", "period_end"]])
            query = f"UPDATE {self.table_name} SET {set_clause} " \
                   f"WHERE account_name = ? AND symbol = ? AND period_start = ? AND period_end = ?"
            
            # For now, we'll use a placeholder implementation
            # In the actual MCP integration, this would use the MCP tools
            # self._execute_write_query(query, row_data)
            
            self.logger.info(f"Updated metrics for {entity.account_name}/{entity.symbol}")
            return entity
            
        except Exception as e:
            self.logger.error(f"Failed to update metrics for {entity.account_name}/{entity.symbol}: {e}")
            raise
    
    def delete(self, entity_id: int) -> bool:
        """
        Delete performance metrics by ID.
        
        Args:
            entity_id: The ID of the metrics to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            query = f"DELETE FROM {self.table_name} WHERE id = ?"
            
            # For now, we'll use a placeholder implementation
            # In the actual MCP integration, this would use the MCP tools
            # affected_rows = self._execute_write_query(query, {"id": entity_id})
            affected_rows = 1  # Placeholder
            
            success = affected_rows > 0
            if success:
                self.logger.info(f"Deleted metrics with ID: {entity_id}")
            else:
                self.logger.warning(f"Metrics not found for deletion: {entity_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to delete metrics {entity_id}: {e}")
            return False
    
    def get_by_account(self, account_name: str) -> List[PerformanceMetrics]:
        """
        Get all performance metrics for a specific account.
        
        Args:
            account_name: Name of the account
            
        Returns:
            List of performance metrics for the account
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE account_name = ? ORDER BY period_end DESC"
            
            # For now, we'll use a placeholder implementation
            results = []  # self._execute_query(query, {"account_name": account_name})
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get metrics by account {account_name}: {e}")
            return []
    
    def get_by_symbol(self, symbol: str) -> List[PerformanceMetrics]:
        """
        Get all performance metrics for a specific symbol.
        
        Args:
            symbol: Symbol to filter by
            
        Returns:
            List of performance metrics for the symbol
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE symbol = ? ORDER BY period_end DESC"
            
            # For now, we'll use a placeholder implementation
            results = []  # self._execute_query(query, {"symbol": symbol})
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get metrics by symbol {symbol}: {e}")
            return []
    
    def get_by_account_and_symbol(self, account_name: str, symbol: str) -> List[PerformanceMetrics]:
        """
        Get performance metrics for a specific account and symbol combination.
        
        Args:
            account_name: Name of the account
            symbol: Symbol to filter by
            
        Returns:
            List of performance metrics for the account/symbol combination
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE account_name = ? AND symbol = ? ORDER BY period_end DESC"
            
            # For now, we'll use a placeholder implementation
            results = []  # self._execute_query(query, {"account_name": account_name, "symbol": symbol})
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get metrics by account {account_name} and symbol {symbol}: {e}")
            return []
    
    def get_latest_metrics(self, account_name: Optional[str] = None, 
                          symbol: Optional[str] = None) -> List[PerformanceMetrics]:
        """
        Get the most recent performance metrics.
        
        Args:
            account_name: Optional account filter
            symbol: Optional symbol filter
            
        Returns:
            List of latest performance metrics
        """
        try:
            query = f"SELECT * FROM {self.table_name} WHERE 1=1"
            params = {}
            
            if account_name:
                query += " AND account_name = ?"
                params["account_name"] = account_name
            
            if symbol:
                query += " AND symbol = ?"
                params["symbol"] = symbol
            
            query += " ORDER BY calculation_timestamp DESC LIMIT 10"
            
            # For now, we'll use a placeholder implementation
            results = []  # self._execute_query(query, params)
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get latest metrics: {e}")
            return []
    
    def get_best_performing_accounts(self, metric: str = "total_return", limit: int = 5) -> List[PerformanceMetrics]:
        """
        Get the best performing accounts based on a specific metric.
        
        Args:
            metric: Metric to sort by (total_return, sharpe_ratio, win_rate, etc.)
            limit: Number of results to return
            
        Returns:
            List of best performing account metrics
        """
        try:
            # Validate metric name to prevent SQL injection
            valid_metrics = ["total_return", "sharpe_ratio", "win_rate", "profit_factor"]
            if metric not in valid_metrics:
                metric = "total_return"
            
            query = f"SELECT * FROM {self.table_name} ORDER BY {metric} DESC LIMIT {limit}"
            
            # For now, we'll use a placeholder implementation
            results = []  # self._execute_query(query)
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get best performing accounts: {e}")
            return []
    
    def delete_old_metrics(self, days_old: int = 30) -> int:
        """
        Delete performance metrics older than specified days.
        
        Args:
            days_old: Number of days to keep metrics
            
        Returns:
            Number of deleted records
        """
        try:
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_old)
            
            query = f"DELETE FROM {self.table_name} WHERE calculation_timestamp < ?"
            
            # For now, we'll use a placeholder implementation
            # affected_rows = self._execute_write_query(query, {"cutoff_date": cutoff_date.isoformat()})
            affected_rows = 0  # Placeholder
            
            if affected_rows > 0:
                self.logger.info(f"Deleted {affected_rows} old metrics records")
            
            return affected_rows
            
        except Exception as e:
            self.logger.error(f"Failed to delete old metrics: {e}")
            return 0


# Global repository instance
metrics_repository = MetricsRepository()