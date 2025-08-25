"""
Database initialization script for the Trading Optimization Platform.
"""

import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from trading_platform.database.connection import db_manager, init_database
from trading_platform.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_database():
    """Initialize the database with all tables and indexes."""
    try:
        logger.info("Starting database initialization...")
        logger.info(f"Database URL: {db_manager._mask_url(config.DATABASE_URL)}")
        
        # Initialize database and create tables
        init_database()
        
        # Verify database health
        if db_manager.health_check():
            logger.info("Database initialization completed successfully!")
            
            # Print database info
            db_info = db_manager.get_database_info()
            logger.info(f"Database info: {db_info}")
            
            return True
        else:
            logger.error("Database health check failed after initialization")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False


def reset_database():
    """Reset the database by dropping and recreating all tables."""
    try:
        logger.warning("Resetting database - all data will be lost!")
        
        # Ask for confirmation
        response = input("Are you sure you want to reset the database? (yes/no): ")
        if response.lower() != 'yes':
            logger.info("Database reset cancelled")
            return False
        
        from trading_platform.database.connection import reset_database
        reset_database()
        
        logger.info("Database reset completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        return False


def check_database():
    """Check database status and connectivity."""
    try:
        logger.info("Checking database status...")
        
        # Initialize if needed
        if not db_manager._initialized:
            db_manager.initialize()
        
        # Health check
        if db_manager.health_check():
            logger.info("Database is healthy and accessible")
            
            # Get and display database info
            db_info = db_manager.get_database_info()
            for key, value in db_info.items():
                logger.info(f"  {key}: {value}")
            
            return True
        else:
            logger.error("Database health check failed")
            return False
            
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        return False


def backup_database(backup_path: str = None):
    """Create a backup of the database."""
    try:
        logger.info("Creating database backup...")
        
        backup_file = db_manager.backup_database(backup_path)
        logger.info(f"Database backup created: {backup_file}")
        return backup_file
        
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database management for Trading Optimization Platform")
    parser.add_argument("command", choices=["init", "reset", "check", "backup"], 
                       help="Database command to execute")
    parser.add_argument("--backup-path", help="Path for database backup file")
    
    args = parser.parse_args()
    
    if args.command == "init":
        success = initialize_database()
        sys.exit(0 if success else 1)
    
    elif args.command == "reset":
        success = reset_database()
        sys.exit(0 if success else 1)
    
    elif args.command == "check":
        success = check_database()
        sys.exit(0 if success else 1)
    
    elif args.command == "backup":
        backup_file = backup_database(args.backup_path)
        sys.exit(0 if backup_file else 1)