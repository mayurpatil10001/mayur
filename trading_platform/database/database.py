"""
Database session management for the Trading Platform API.

This module provides database session management and connection handling
for the FastAPI application.

Requirements: 2.1, 2.3, 10.1
"""

import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from ..config import config
from .connection import DatabaseManager

logger = logging.getLogger(__name__)

# Database engine and session factory
engine = None
SessionLocal = None


def init_database():
    """Initialize database engine and session factory."""
    global engine, SessionLocal
    
    if engine is None:
        # Create SQLite engine
        database_url = config.DATABASE_URL
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},  # SQLite specific
            echo=False  # Set to True for SQL debugging
        )
        
        SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine
        )
        
        logger.info(f"Database initialized: {database_url}")


def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.
    
    Yields:
        SQLAlchemy database session
    """
    if SessionLocal is None:
        init_database()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Get database session as context manager.
    
    Yields:
        SQLAlchemy database session
    """
    if SessionLocal is None:
        init_database()
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_manager() -> DatabaseManager:
    """
    Get simple database manager for direct SQL operations.
    
    Returns:
        DatabaseManager instance
    """
    # Extract database path from URL
    db_path = config.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    return DatabaseManager(db_path)


# Initialize database on module import
init_database()