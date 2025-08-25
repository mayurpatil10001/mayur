#!/usr/bin/env python3
"""
Simple database connection for validation services.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Simple SQLite database connection."""

    def __init__(self, db_path: str = "trading_platform.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.connection: Optional[sqlite3.Connection] = None
        self.connect()

    def connect(self) -> None:
        """Connect to the database."""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row  # Enable column access by name
            logger.debug(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Error connecting to database {self.db_path}: {e}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.debug("Database connection closed")

    def execute_query(self, query: str, params: tuple = ()) -> list:
        """Execute a SELECT query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            List of rows as dictionaries
        """
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT, UPDATE, or DELETE query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Number of affected rows
        """
        if not self.connection:
            self.connect()

        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error executing write query: {e}")
            raise

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

# Global database manager instance
_db_manager = None


def get_db_session():
    """Get database session (compatibility function)."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def get_db():
    """Get database connection (compatibility function)."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


# Alias for backward compatibility
DatabaseConnection = DatabaseManager