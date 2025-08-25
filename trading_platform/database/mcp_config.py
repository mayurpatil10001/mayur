"""
MCP Configuration module for database operations.

This module handles configuration settings for MCP (Model Context Protocol)
database operations, including connection parameters and authentication.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MCPServerConfig:
    """Configuration for an MCP server."""
    command: str
    args: list[str]
    env: Dict[str, str]
    disabled: bool = False
    auto_approve: list[str] = None
    
    def __post_init__(self):
        if self.auto_approve is None:
            self.auto_approve = []


@dataclass
class MCPDatabaseConfig:
    """Configuration for MCP database operations."""
    database_path: str = "./trading_platform.db"
    server_name: str = "sqlite"
    connection_timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_logging: bool = True
    log_level: str = "INFO"
    
    def __post_init__(self):
        # Ensure database path is absolute
        if not os.path.isabs(self.database_path):
            self.database_path = os.path.abspath(self.database_path)


class MCPConfigManager:
    """
    Manages MCP configuration settings.
    
    This class handles loading, saving, and validating MCP configuration
    for database operations.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to the MCP configuration file
        """
        self.config_path = config_path or self._get_default_config_path()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._config = None
        self._server_configs = {}
    
    def _get_default_config_path(self) -> str:
        """Get the default configuration file path."""
        # Check workspace-level config first
        workspace_config = ".kiro/settings/mcp.json"
        if os.path.exists(workspace_config):
            return workspace_config
        
        # Check user-level config
        user_config = os.path.expanduser("~/.kiro/settings/mcp.json")
        if os.path.exists(user_config):
            return user_config
        
        # Default to workspace config path
        return workspace_config
    
    def load_config(self) -> MCPDatabaseConfig:
        """
        Load MCP configuration from file.
        
        Returns:
            MCPDatabaseConfig instance
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        try:
            if not os.path.exists(self.config_path):
                self.logger.warning(f"Config file not found: {self.config_path}")
                return self._get_default_config()
            
            with open(self.config_path, 'r') as f:
                config_data = json.load(f)
            
            # Load server configurations
            mcp_servers = config_data.get('mcpServers', {})
            for server_name, server_config in mcp_servers.items():
                self._server_configs[server_name] = MCPServerConfig(
                    command=server_config.get('command', ''),
                    args=server_config.get('args', []),
                    env=server_config.get('env', {}),
                    disabled=server_config.get('disabled', False),
                    auto_approve=server_config.get('autoApprove', [])
                )
            
            # Create database config
            sqlite_config = mcp_servers.get('sqlite', {})
            db_path = self._extract_db_path_from_args(sqlite_config.get('args', []))
            
            self._config = MCPDatabaseConfig(
                database_path=db_path or "./trading_platform.db",
                server_name="sqlite",
                connection_timeout=30,
                max_retries=3,
                retry_delay=1.0,
                enable_logging=True,
                log_level=sqlite_config.get('env', {}).get('FASTMCP_LOG_LEVEL', 'INFO')
            )
            
            self.logger.info(f"Loaded MCP config from {self.config_path}")
            return self._config
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in config file: {str(e)}")
            raise ValueError(f"Invalid JSON in config file: {str(e)}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {str(e)}")
            raise
    
    def _extract_db_path_from_args(self, args: list[str]) -> Optional[str]:
        """
        Extract database path from MCP server arguments.
        
        Args:
            args: List of command arguments
            
        Returns:
            Database path if found, None otherwise
        """
        try:
            if '--db-path' in args:
                db_path_index = args.index('--db-path')
                if db_path_index + 1 < len(args):
                    return args[db_path_index + 1]
        except (ValueError, IndexError):
            pass
        
        return None
    
    def _get_default_config(self) -> MCPDatabaseConfig:
        """
        Get default MCP configuration.
        
        Returns:
            Default MCPDatabaseConfig instance
        """
        self.logger.info("Using default MCP configuration")
        return MCPDatabaseConfig()
    
    def save_config(self, config: MCPDatabaseConfig) -> None:
        """
        Save MCP configuration to file.
        
        Args:
            config: MCPDatabaseConfig to save
        """
        try:
            # Ensure directory exists
            config_dir = os.path.dirname(self.config_path)
            os.makedirs(config_dir, exist_ok=True)
            
            # Load existing config or create new one
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                config_data = {"mcpServers": {}}
            
            # Update SQLite server config
            sqlite_server_config = {
                "command": "uvx",
                "args": [
                    "mcp-server-sqlite",
                    "--db-path",
                    config.database_path
                ],
                "env": {
                    "FASTMCP_LOG_LEVEL": config.log_level
                },
                "disabled": False,
                "autoApprove": [
                    "read_query",
                    "write_query",
                    "list_tables",
                    "describe_table",
                    "create_table"
                ]
            }
            
            config_data["mcpServers"]["sqlite"] = sqlite_server_config
            
            # Write config file
            with open(self.config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            self._config = config
            self.logger.info(f"Saved MCP config to {self.config_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to save config: {str(e)}")
            raise
    
    def get_server_config(self, server_name: str) -> Optional[MCPServerConfig]:
        """
        Get configuration for a specific MCP server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            MCPServerConfig if found, None otherwise
        """
        return self._server_configs.get(server_name)
    
    def is_server_enabled(self, server_name: str) -> bool:
        """
        Check if an MCP server is enabled.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            True if server is enabled, False otherwise
        """
        server_config = self.get_server_config(server_name)
        return server_config is not None and not server_config.disabled
    
    def get_auto_approved_tools(self, server_name: str) -> list[str]:
        """
        Get list of auto-approved tools for a server.
        
        Args:
            server_name: Name of the MCP server
            
        Returns:
            List of auto-approved tool names
        """
        server_config = self.get_server_config(server_name)
        return server_config.auto_approve if server_config else []
    
    def validate_config(self, config: MCPDatabaseConfig) -> bool:
        """
        Validate MCP configuration.
        
        Args:
            config: MCPDatabaseConfig to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check database path
            if not config.database_path:
                self.logger.error("Database path is required")
                return False
            
            # Check if database directory exists or can be created
            db_dir = os.path.dirname(config.database_path)
            if db_dir and not os.path.exists(db_dir):
                try:
                    os.makedirs(db_dir, exist_ok=True)
                except OSError as e:
                    self.logger.error(f"Cannot create database directory: {str(e)}")
                    return False
            
            # Check timeout values
            if config.connection_timeout <= 0:
                self.logger.error("Connection timeout must be positive")
                return False
            
            if config.max_retries < 0:
                self.logger.error("Max retries cannot be negative")
                return False
            
            if config.retry_delay < 0:
                self.logger.error("Retry delay cannot be negative")
                return False
            
            # Check log level
            valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if config.log_level.upper() not in valid_log_levels:
                self.logger.error(f"Invalid log level: {config.log_level}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Config validation failed: {str(e)}")
            return False


# Global configuration manager instance
_config_manager = None


def get_config_manager() -> MCPConfigManager:
    """
    Get the global MCP configuration manager.
    
    Returns:
        MCPConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = MCPConfigManager()
    return _config_manager


def get_mcp_config() -> MCPDatabaseConfig:
    """
    Get the current MCP database configuration.
    
    Returns:
        MCPDatabaseConfig instance
    """
    config_manager = get_config_manager()
    return config_manager.load_config()


def save_mcp_config(config: MCPDatabaseConfig) -> None:
    """
    Save MCP database configuration.
    
    Args:
        config: MCPDatabaseConfig to save
    """
    config_manager = get_config_manager()
    config_manager.save_config(config)