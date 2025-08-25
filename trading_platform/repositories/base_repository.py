"""
Base repository interface and abstract class for database operations.

This module provides the foundation for all repository implementations
using the MCP database integration.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generic, TypeVar, Union
from datetime import datetime
import logging

# Type variable for generic repository
T = TypeVar('T')

logger = logging.getLogger(__name__)


class IRepository(ABC, Generic[T]):
    """
    Generic repository interface for database operations.
    
    This interface defines the standard CRUD operations that all
    repositories should implement.
    """
    
    @abstractmethod
    def create(self, entity: T) -> T:
        """
        Create a new entity in the database.
        
        Args:
            entity: The entity to create
            
        Returns:
            The created entity with any generated fields
        """
        pass
    
    @abstractmethod
    def get_by_id(self, entity_id: Union[str, int]) -> Optional[T]:
        """
        Retrieve an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to retrieve
            
        Returns:
            The entity if found, None otherwise
        """
        pass
    
    @abstractmethod
    def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """
        Retrieve all entities with optional pagination.
        
        Args:
            limit: Maximum number of entities to return
            offset: Number of entities to skip
            
        Returns:
            List of entities
        """
        pass
    
    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Update an existing entity in the database.
        
        Args:
            entity: The entity to update
            
        Returns:
            The updated entity
        """
        pass
    
    @abstractmethod
    def delete(self, entity_id: Union[str, int]) -> bool:
        """
        Delete an entity by its ID.
        
        Args:
            entity_id: The ID of the entity to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pass
    
    @abstractmethod
    def exists(self, entity_id: Union[str, int]) -> bool:
        """
        Check if an entity exists by its ID.
        
        Args:
            entity_id: The ID of the entity to check
            
        Returns:
            True if entity exists, False otherwise
        """
        pass
    
    @abstractmethod
    def count(self) -> int:
        """
        Get the total count of entities.
        
        Returns:
            Total number of entities
        """
        pass


class BaseRepository(IRepository[T], ABC):
    """
    Abstract base repository implementation using MCP for database operations.
    
    This class provides common functionality for all repository implementations
    and integrates with the MCP database client.
    """
    
    def __init__(self, table_name: str):
        """
        Initialize the base repository.
        
        Args:
            table_name: Name of the database table this repository manages
        """
        self.table_name = table_name
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize MCP wrapper with tool injection
        self._mcp_wrapper = None
        self._initialize_mcp_wrapper()
    
    def _initialize_mcp_wrapper(self):
        """Initialize the MCP wrapper with actual MCP tools."""
        try:
            from ..database.mcp_kiro_wrapper import create_kiro_mcp_wrapper, get_mcp_tools_injector
            
            # Create MCP wrapper
            self._mcp_wrapper = create_kiro_mcp_wrapper()
            
            # Create tools injector
            injector = get_mcp_tools_injector(self._mcp_wrapper)
            
            # Define wrapper functions that will call the actual MCP tools
            # These will be overridden by the repository implementations that have access to MCP tools
            def read_query_tool(query: str):
                """Placeholder for mcp_sqlite_read_query tool."""
                raise NotImplementedError(
                    "MCP read query tool not injected. "
                    "Repository must inject actual MCP tools."
                )
            
            def write_query_tool(query: str):
                """Placeholder for mcp_sqlite_write_query tool."""
                raise NotImplementedError(
                    "MCP write query tool not injected. "
                    "Repository must inject actual MCP tools."
                )
            
            def list_tables_tool():
                """Placeholder for mcp_sqlite_list_tables tool."""
                raise NotImplementedError(
                    "MCP list tables tool not injected. "
                    "Repository must inject actual MCP tools."
                )
            
            def describe_table_tool(table_name: str):
                """Placeholder for mcp_sqlite_describe_table tool."""
                raise NotImplementedError(
                    "MCP describe table tool not injected. "
                    "Repository must inject actual MCP tools."
                )
            
            def create_table_tool(create_statement: str):
                """Placeholder for mcp_sqlite_create_table tool."""
                raise NotImplementedError(
                    "MCP create table tool not injected. "
                    "Repository must inject actual MCP tools."
                )
            
            # Inject placeholder tools (will be replaced by actual tools in concrete repositories)
            injector.inject_all_tools(
                read_query_tool,
                write_query_tool,
                list_tables_tool,
                describe_table_tool,
                create_table_tool
            )
            
            self.logger.debug(f"Initialized MCP wrapper for table: {self.table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize MCP wrapper: {e}")
            self._mcp_wrapper = None
    
    def _execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query using MCP wrapper.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters (not used in current implementation)
            
        Returns:
            List of result dictionaries
        """
        try:
            if self._mcp_wrapper is None:
                raise RuntimeError("MCP wrapper not initialized")
            
            self.logger.debug(f"Executing query on {self.table_name}: {query}")
            return self._mcp_wrapper.execute_query(query)
        except Exception as e:
            self.logger.error(f"Query execution failed: {e}")
            raise
    
    def _execute_write_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query using MCP wrapper.
        
        Args:
            query: SQL query to execute
            params: Optional query parameters (not used in current implementation)
            
        Returns:
            Number of affected rows
        """
        try:
            if self._mcp_wrapper is None:
                raise RuntimeError("MCP wrapper not initialized")
            
            self.logger.debug(f"Executing write query on {self.table_name}: {query}")
            return self._mcp_wrapper.execute_write_query(query)
        except Exception as e:
            self.logger.error(f"Write query execution failed: {e}")
            raise
    
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
            # Use parameterized query format for SQLite
            query = f"SELECT * FROM {self.table_name} WHERE {id_field} = '{entity_id}'"
            
            results = self._execute_query(query)
            
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
            
            results = self._execute_query(query)
            
            return [self._map_row_to_entity(row) for row in results]
            
        except Exception as e:
            self.logger.error(f"Failed to get all entities: {e}")
            raise
    
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
            
            results = self._execute_query(query)
            
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
            
            results = self._execute_query(query)
            
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
            if self._mcp_wrapper:
                try:
                    tables = self._mcp_wrapper.list_tables()
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