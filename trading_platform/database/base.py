"""
Database base configuration.
"""

from sqlalchemy.orm import declarative_base

# Create the base class for all ORM models
Base = declarative_base()

__all__ = ['Base']