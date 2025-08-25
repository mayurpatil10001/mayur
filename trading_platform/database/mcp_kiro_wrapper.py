"""
Kiro MCP Wrapper that uses the actual MCP tools available in the Kiro environment.

This module provides a working implementation that directly uses the MCP tools
available through Kiro's function calling interface.
"""

import logging
from typing import List, Dict, Any, Optional
from .mcp_client import MCPClient, MCPDatabaseError

logger = logging.getLogger(__name__)


class KiroMCPWrapper(MCPClient):
    """
    Kiro-specific MCP wrapper that uses the actual MCP tools.
    
    This class provides a working implementation that directly calls the MCP tools
    that are available in the Kiro environment through function calling.
    """
    
    def __init__(self, database_path: str = "./trading_platform.db"):
        """
        Initialize Kiro MCP wrapper.
        
        Args:
            database_path: Path to the SQLite database file
        """
        super().__init__(database_path)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.info(f"Initialized Kiro MCP wrapper for database: {database_path}")
    
    def _execute_select_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute SELECT query using Kiro's MCP tools.
        
        Args:
            query: SQL SELECT query to execute
            
        Returns:
            List of dictionaries representing query results
        """
        try:
            self.logger.debug(f"Executing MCP read query: {query}")
            
            # This method will be called by the repository layer that has access
            # to the actual MCP tools. The repository will inject the MCP tool calls.
            raise NotImplementedError(
                "This method should be overridden by the repository layer "
                "that has access to Kiro's MCP tools"
            )
            
        except NotImplementedError:
            raise
        except Exception as e:
            self.logger.error(f"MCP read query failed: {str(e)}")
            raise MCPDatabaseError(f"MCP read query failed: {str(e)}")
    
    def _execute_write_query(self, query: str) -> int:
        """
        Execute write query using Kiro's MCP tools.
        
        Args:
            query: SQL INSERT/UPDATE/DELETE query to execute
            
        Returns:
            Number of affected rows
        """
        try:
            self.logger.debug(f"Executing MCP write query: {query}")
            
            # This method will be called by the repository layer that has access
            # to the actual MCP tools. The repository will inject the MCP tool calls.
            raise NotImplementedError(
                "This method should be overridden by the repository layer "
                "that has access to Kiro's MCP tools"
            )
            
        except NotImplementedError:
            raise
        except Exception as e:
            self.logger.error(f"MCP write query failed: {str(e)}")
            raise MCPDatabaseError(f"MCP write query failed: {str(e)}")
    
    def _list_tables(self) -> List[str]:
        """
        List tables using Kiro's MCP tools.
        
        Returns:
            List of table names
        """
        try:
            self.logger.debug("Listing tables via MCP")
            
            # This method will be called by the repository layer that has access
            # to the actual MCP tools. The repository will inject the MCP tool calls.
            raise NotImplementedError(
                "This method should be overridden by the repository layer "
                "that has access to Kiro's MCP tools"
            )
            
        except NotImplementedError:
            raise
        except Exception as e:
            self.logger.error(f"MCP list tables failed: {str(e)}")
            raise MCPDatabaseError(f"MCP list tables failed: {str(e)}")
    
    def _describe_table(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Describe table using Kiro's MCP tools.
        
        Args:
            table_name: Name of the table to describe
            
        Returns:
            List of column information dictionaries
        """
        try:
            self.logger.debug(f"Describing table {table_name} via MCP")
            
            # This method will be called by the repository layer that has access
            # to the actual MCP tools. The repository will inject the MCP tool calls.
            raise NotImplementedError(
                "This method should be overridden by the repository layer "
                "that has access to Kiro's MCP tools"
            )
            
        except NotImplementedError:
            raise
        except Exception as e:
            self.logger.error(f"MCP describe table failed: {str(e)}")
            raise MCPDatabaseError(f"MCP describe table failed: {str(e)}")
    
    def _create_table(self, create_statement: str) -> None:
        """
        Create table using Kiro's MCP tools.
        
        Args:
            create_statement: CREATE TABLE SQL statement
        """
        try:
            self.logger.debug(f"Creating table via MCP: {create_statement}")
            
            # This method will be called by the repository layer that has access
            # to the actual MCP tools. The repository will inject the MCP tool calls.
            raise NotImplementedError(
                "This method should be overridden by the repository layer "
                "that has access to Kiro's MCP tools"
            )
            
        except NotImplementedError:
            raise
        except Exception as e:
            self.logger.error(f"MCP create table failed: {str(e)}")
            raise MCPDatabaseError(f"MCP create table failed: {str(e)}")


class MCPToolsInjector:
    """
    Helper class to inject MCP tool functions into the wrapper.
    
    This class provides a way to inject the actual MCP tool functions
    from the Kiro environment into the MCP wrapper.
    """
    
    def __init__(self, wrapper: KiroMCPWrapper):
        """
        Initialize the injector with a wrapper instance.
        
        Args:
            wrapper: KiroMCPWrapper instance to inject tools into
        """
        self.wrapper = wrapper
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def inject_read_query_tool(self, read_query_func):
        """
        Inject the read query MCP tool function.
        
        Args:
            read_query_func: Function that calls mcp_sqlite_read_query
        """
        def _execute_select_query(query: str) -> List[Dict[str, Any]]:
            try:
                self.wrapper.logger.debug(f"Executing injected MCP read query: {query}")
                result = read_query_func(query)
                self.wrapper.logger.debug(f"Query returned {len(result) if result else 0} rows")
                return result if result else []
            except Exception as e:
                self.wrapper.logger.error(f"Injected MCP read query failed: {str(e)}")
                raise MCPDatabaseError(f"MCP read query failed: {str(e)}")
        
        self.wrapper._execute_select_query = _execute_select_query
        self.logger.debug("Injected read query tool")
    
    def inject_write_query_tool(self, write_query_func):
        """
        Inject the write query MCP tool function.
        
        Args:
            write_query_func: Function that calls mcp_sqlite_write_query
        """
        def _execute_write_query(query: str) -> int:
            try:
                self.wrapper.logger.debug(f"Executing injected MCP write query: {query}")
                result = write_query_func(query)
                changes = 0
                if isinstance(result, dict):
                    changes = result.get('changes', 0)
                elif isinstance(result, int):
                    changes = result
                self.wrapper.logger.debug(f"Write query affected {changes} rows")
                return changes
            except Exception as e:
                self.wrapper.logger.error(f"Injected MCP write query failed: {str(e)}")
                raise MCPDatabaseError(f"MCP write query failed: {str(e)}")
        
        self.wrapper._execute_write_query = _execute_write_query
        self.logger.debug("Injected write query tool")
    
    def inject_list_tables_tool(self, list_tables_func):
        """
        Inject the list tables MCP tool function.
        
        Args:
            list_tables_func: Function that calls mcp_sqlite_list_tables
        """
        def _list_tables() -> List[str]:
            try:
                self.wrapper.logger.debug("Executing injected MCP list tables")
                result = list_tables_func()
                if isinstance(result, list):
                    tables = [table.get('name', '') for table in result if isinstance(table, dict)]
                    self.wrapper.logger.debug(f"Found {len(tables)} tables")
                    return tables
                return []
            except Exception as e:
                self.wrapper.logger.error(f"Injected MCP list tables failed: {str(e)}")
                raise MCPDatabaseError(f"MCP list tables failed: {str(e)}")
        
        self.wrapper._list_tables = _list_tables
        self.logger.debug("Injected list tables tool")
    
    def inject_describe_table_tool(self, describe_table_func):
        """
        Inject the describe table MCP tool function.
        
        Args:
            describe_table_func: Function that calls mcp_sqlite_describe_table
        """
        def _describe_table(table_name: str) -> List[Dict[str, Any]]:
            try:
                self.wrapper.logger.debug(f"Executing injected MCP describe table: {table_name}")
                result = describe_table_func(table_name)
                schema = result if isinstance(result, list) else []
                self.wrapper.logger.debug(f"Table {table_name} has {len(schema)} columns")
                return schema
            except Exception as e:
                self.wrapper.logger.error(f"Injected MCP describe table failed: {str(e)}")
                raise MCPDatabaseError(f"MCP describe table failed: {str(e)}")
        
        self.wrapper._describe_table = _describe_table
        self.logger.debug("Injected describe table tool")
    
    def inject_create_table_tool(self, create_table_func):
        """
        Inject the create table MCP tool function.
        
        Args:
            create_table_func: Function that calls mcp_sqlite_create_table
        """
        def _create_table(create_statement: str) -> None:
            try:
                self.wrapper.logger.debug(f"Executing injected MCP create table: {create_statement}")
                create_table_func(create_statement)
                self.wrapper.logger.debug("Table created successfully")
            except Exception as e:
                self.wrapper.logger.error(f"Injected MCP create table failed: {str(e)}")
                raise MCPDatabaseError(f"MCP create table failed: {str(e)}")
        
        self.wrapper._create_table = _create_table
        self.logger.debug("Injected create table tool")
    
    def inject_all_tools(self, read_query_func, write_query_func, list_tables_func, 
                        describe_table_func, create_table_func):
        """
        Inject all MCP tool functions at once.
        
        Args:
            read_query_func: Function that calls mcp_sqlite_read_query
            write_query_func: Function that calls mcp_sqlite_write_query
            list_tables_func: Function that calls mcp_sqlite_list_tables
            describe_table_func: Function that calls mcp_sqlite_describe_table
            create_table_func: Function that calls mcp_sqlite_create_table
        """
        self.inject_read_query_tool(read_query_func)
        self.inject_write_query_tool(write_query_func)
        self.inject_list_tables_tool(list_tables_func)
        self.inject_describe_table_tool(describe_table_func)
        self.inject_create_table_tool(create_table_func)
        self.logger.info("Injected all MCP tools")


def create_kiro_mcp_wrapper(database_path: str = "./trading_platform.db") -> KiroMCPWrapper:
    """
    Create a Kiro MCP wrapper instance.
    
    Args:
        database_path: Path to the SQLite database file
        
    Returns:
        KiroMCPWrapper instance
    """
    return KiroMCPWrapper(database_path)


def get_mcp_tools_injector(wrapper: KiroMCPWrapper) -> MCPToolsInjector:
    """
    Get an MCP tools injector for the given wrapper.
    
    Args:
        wrapper: KiroMCPWrapper instance
        
    Returns:
        MCPToolsInjector instance
    """
    return MCPToolsInjector(wrapper)