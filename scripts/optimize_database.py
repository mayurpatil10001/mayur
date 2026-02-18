#!/usr/bin/env python3
"""
Database optimization script to add indexes for better performance.
"""

import sqlite3
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def optimize_database():
    """Add indexes to improve query performance."""
    
    db_path = Path("trading_platform.db")
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if indexes already exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing_indexes = [row[0] for row in cursor.fetchall()]
        
        indexes_to_create = [
            ("idx_processed_trades_account_symbol", "CREATE INDEX IF NOT EXISTS idx_processed_trades_account_symbol ON processed_trades(account_name, symbol)"),
            ("idx_processed_trades_account", "CREATE INDEX IF NOT EXISTS idx_processed_trades_account ON processed_trades(account_name)"),
            ("idx_processed_trades_symbol", "CREATE INDEX IF NOT EXISTS idx_processed_trades_symbol ON processed_trades(symbol)"),
            ("idx_processed_trades_entry_time", "CREATE INDEX IF NOT EXISTS idx_processed_trades_entry_time ON processed_trades(entry_time)"),
            ("idx_processed_trades_profit_loss", "CREATE INDEX IF NOT EXISTS idx_processed_trades_profit_loss ON processed_trades(profit_loss)"),
            ("idx_processed_trades_day_hour", "CREATE INDEX IF NOT EXISTS idx_processed_trades_day_hour ON processed_trades(day_of_week, hour_of_day)")
        ]
        
        created_count = 0
        for index_name, create_sql in indexes_to_create:
            if index_name not in existing_indexes:
                logger.info(f"Creating index: {index_name}")
                cursor.execute(create_sql)
                created_count += 1
            else:
                logger.info(f"Index already exists: {index_name}")
        
        # Analyze tables to update statistics
        logger.info("Analyzing tables to update query planner statistics...")
        cursor.execute("ANALYZE")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database optimization complete. Created {created_count} new indexes.")
        return True
        
    except Exception as e:
        logger.error(f"Error optimizing database: {e}")
        return False

if __name__ == "__main__":
    optimize_database()