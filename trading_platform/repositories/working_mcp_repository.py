"""
Working MCP repository that uses actual MCP tools.

This module provides a repository implementation that works with the actual
MCP tools available in the current environment.
"""

import logging
from typing import List, Dict, Any, Optional, Union, Generic, TypeVar
from datetime import datetime
from abc import ABC, abstractmethod

# Type variable for generic repository
T = TypeVar('T')

logger = logging.getLogger(__name__)


class WorkingMCPRepository(Generic[T], ABC):
    """
    Working MCP repository that uses actual MCP tools.
    
    This repository implementation is designed to work with the actual MCP tools
    that are available in the current environment through direct function calls.
    """
    
    def __init__(self, table_name: str):
        """
        Initialize the working MCP repository.
        
        Args:
            table_name: Name of the database table this repository manages
        """
        self.table_name = table_name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"Initialized working MCP repository for table: {table_name}")
    
    def execute_read_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query using MCP tools.
        
        This method is designed to be overridden by the calling context
        that has access to the actual MCP tools.
        
        Args:
            query: SQL SELECT query to execute
            
        Returns:
            List of result dictionaries
        """
        self.logger.debug(f"Executing read query: {query}")
        raise NotImplementedError(
            "This method must be overridden by the calling context "
            "that has access to mcp_sqlite_read_query"
        )
    
    def execute_write_query(self, query: str) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query using MCP tools.
        
        This method is designed to be overridden by the calling context
        that has access to the actual MCP tools.
        
        Args:
            query: SQL query to execute
            
        Returns:
            Number of affected rows
        """
        self.logger.debug(f"Executing write query: {query}")
        raise NotImplementedError(
            "This method must be overridden by the calling context "
            "that has access to mcp_sqlite_write_query"
        )
    
    def list_tables(self) -> List[str]:
        """
        List all tables in the database using MCP tools.
        
        This method is designed to be overridden by the calling context
        that has access to the actual MCP tools.
        
        Returns:
            List of table names
        """
        self.logger.debug("Listing tables")
        raise NotImplementedError(
            "This method must be overridden by the calling context "
            "that has access to mcp_sqlite_list_tables"
        )
    
    def describe_table(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a table using MCP tools.
        
        This method is designed to be overridden by the calling context
        that has access to the actual MCP tools.
        
        Args:
            table_name: Name of the table to describe
            
        Returns:
            List of column information dictionaries
        """
        self.logger.debug(f"Describing table: {table_name}")
        raise NotImplementedError(
            "This method must be overridden by the calling context "
            "that has access to mcp_sqlite_describe_table"
        )
    
    def create_table(self, create_statement: str) -> None:
        """
        Create a table using MCP tools.
        
        This method is designed to be overridden by the calling context
        that has access to the actual MCP tools.
        
        Args:
            create_statement: CREATE TABLE SQL statement
        """
        self.logger.debug(f"Creating table: {create_statement}")
        raise NotImplementedError(
            "This method must be overridden by the calling context "
            "that has access to mcp_sqlite_create_table"
        )
    
    # Abstract methods that concrete repositories must implement
    
    @abstractmethod
    def _map_row_to_entity(self, row: Dict[str, Any]) -> T:
        """
        Map a database row to an entity object.
        
        Args:
            row: Database row as dictionary
            
        Returns:
            Entity object
        """
        pass
    
    @abstractmethod
    def _map_entity_to_row(self, entity: T) -> Dict[str, Any]:
        """
        Map an entity object to a database row.
        
        Args:
            entity: Entity object
            
        Returns:
            Database row as dictionary
        """
        pass
    
    @abstractmethod
    def _get_id_field_name(self) -> str:
        """
        Get the name of the ID field for this entity.
        
        Returns:
            Name of the ID field
        """
        pass
    
    # Standard CRUD operations
    
    def get_by_id(self, entity_id: Union[str, int]) -> Optional[T]:
        """
        Retrieve an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to retrieve
            
        Returns:
            The entity if found, None otherwise
        """
        try:
            id_field = self._get_id_field_name()
            query = f"SELECT * FROM {self.table_name} WHERE {id_field} = '{entity_id}'"
            
            results = self.execute_read_query(query)
            
            if results:
                return self._map_row_to_entity(results[0])
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get entity by ID {entity_id}: {e}")
            raise
    
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """
        Retrieve all entities with optional pagination.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entities
        """
        try:
            query = f"SELECT * FROM {self.table_name}"
            
            if limit is not None:
                query += f" LIMIT {limit}"
                if offset is not None:
                    query += f" OFFSET {offset}"
            
            results = self.execute_read_query(query)
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get all entities: {e}")
            raise
    
    def create(self, entity: T) -> T:
        """
        Create a new entity in the database.
        
        Args:
            entity: The entity to create
            
        Returns:
            The created entity
        """
        try:
            row_data = self._map_entity_to_row(entity)
            
            # Build INSERT query
            columns = ", ".join(row_data.keys())
            values = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in row_data.values()])
            query = f"INSERT INTO {self.table_name} ({columns}) VALUES ({values})"
            
            affected_rows = self.execute_write_query(query)
            
            if affected_rows > 0:
                self.logger.info(f"Created entity in {self.table_name}")
                return entity
            else:
                raise RuntimeError("No rows were affected during create operation")
            
        except Exception as e:
            self.logger.error(f"Failed to create entity: {e}")
            raise
    
    def update(self, entity: T) -> T:
        """
        Update an existing entity in the database.
        
        Args:
            entity: The entity to update
            
        Returns:
            The updated entity
        """
        try:
            row_data = self._map_entity_to_row(entity)
            id_field = self._get_id_field_name()
            id_value = row_data[id_field]
            
            # Build UPDATE query
            set_clauses = []
            for key, value in row_data.items():
                if key != id_field:
                    if isinstance(value, str):
                        set_clauses.append(f"{key} = '{value}'")
                    else:
                        set_clauses.append(f"{key} = {value}")
            
            set_clause = ", ".join(set_clauses)
            query = f"UPDATE {self.table_name} SET {set_clause} WHERE {id_field} = '{id_value}'"
            
            affected_rows = self.execute_write_query(query)
            
            if affected_rows > 0:
                self.logger.info(f"Updated entity in {self.table_name}")
                return entity
            else:
                raise RuntimeError("No rows were affected during update operation")
            
        except Exception as e:
            self.logger.error(f"Failed to update entity: {e}")
            raise
    
    def delete(self, entity_id: Union[str, int]) -> bool:
        """
        Delete an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            id_field = self._get_id_field_name()
            query = f"DELETE FROM {self.table_name} WHERE {id_field} = '{entity_id}'"
            
            affected_rows = self.execute_write_query(query)
            
            success = affected_rows > 0
            if success:
                self.logger.info(f"Deleted entity from {self.table_name}: {entity_id}")
            else:
                self.logger.warning(f"Entity not found for deletion: {entity_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Failed to delete entity {entity_id}: {e}")
            return False
    
    def exists(self, entity_id: Union[str, int]) -> bool:
        """
        Check if an entity exists by its ID.
        
        Args:
            entity_id: The ID of the entity to check
            
        Returns:
            True if entity exists, False otherwise
        """
        try:
            id_field = self._get_id_field_name()
            query = f"SELECT 1 FROM {self.table_name} WHERE {id_field} = '{entity_id}' LIMIT 1"
            
            results = self.execute_read_query(query)
            
            return len(results) > 0
            
        except Exception as e:
            self.logger.error(f"Failed to check if entity exists {entity_id}: {e}")
            return False
    
    def count(self) -> int:
        """
        Get the total count of entities.
        
        Returns:
            Total number of entities
        """
        try:
            query = f"SELECT COUNT(*) as count FROM {self.table_name}"
            
            results = self.execute_read_query(query)
            
            if results:
                return results[0].get('count', 0)
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to count entities: {e}")
            return 0
    
    def get_table_info(self) -> Dict[str, Any]:
        """
        Get information about the repository's table.
        
        Returns:
            Dictionary with table information
        """
        try:
            # Check if table exists by trying to list tables
            table_exists = False
            try:
                tables = self.list_tables()
                table_exists = self.table_name in tables
            except Exception:
                # If list_tables fails, assume table exists and let count() handle it
                table_exists = True
            
            return {
                "table_name": self.table_name,
                "exists": table_exists,
                "count": self.count() if table_exists else 0
            }
        except Exception as e:
            self.logger.error(f"Failed to get table info: {e}")
            return {
                "table_name": self.table_name,
                "exists": False,
                "count": 0,
                "error": str(e)
            }
    
    def health_check(self) -> bool:
        """
        Perform a health check on the repository.
        
        Returns:
            True if repository is working correctly
        """
        try:
            # Simple query to test connectivity
            result = self.execute_read_query("SELECT 1 as test")
            return len(result) == 1 and result[0].get('test') == 1
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False