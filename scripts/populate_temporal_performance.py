#!/usr/bin/env python3
"""
Populate temporal_performance table with calculated analytics.

This script calculates temporal performance metrics from processed_trades
and populates the temporal_performance table for the frontend to display.
"""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_connection() -> sqlite3.Connection:
    """Get database connection."""
    db_path = Path("trading_platform.db")
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path.absolute()}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def clear_temporal_performance_table(conn: sqlite3.Connection) -> None:
    """Clear existing temporal performance data."""
    logger.info("Clearing existing temporal_performance data...")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM temporal_performance")
    conn.commit()
    logger.info("Temporal performance table cleared")


def calculate_temporal_metrics(conn: sqlite3.Connection) -> List[Dict]:
    """Calculate temporal performance metrics from processed trades."""
    logger.info("Calculating temporal performance metrics...")
    
    cursor = conn.cursor()
    
    # Query to calculate performance by account, symbol, hour, and day
    query = """
    SELECT 
        account_name,
        symbol,
        hour_of_day,
        day_of_week,
        COUNT(*) as total_trades,
        SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
        SUM(profit_loss) as total_profit_loss,
        AVG(profit_loss) as average_profit_loss,
        ROUND((SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 2) as win_rate
    FROM processed_trades 
    WHERE account_name IS NOT NULL 
        AND symbol IS NOT NULL 
        AND hour_of_day IS NOT NULL 
        AND day_of_week IS NOT NULL
        AND profit_loss IS NOT NULL
    GROUP BY account_name, symbol, hour_of_day, day_of_week
    HAVING COUNT(*) >= 5  -- Only include combinations with at least 5 trades
    ORDER BY account_name, symbol, hour_of_day, day_of_week
    """
    
    cursor.execute(query)
    results = cursor.fetchall()
    
    metrics = []
    for row in results:
        metrics.append({
            'account_name': row['account_name'],
            'base_symbol': row['symbol'],
            'hour_of_day': row['hour_of_day'],
            'day_of_week': row['day_of_week'],
            'total_trades': row['total_trades'],
            'winning_trades': row['winning_trades'],
            'total_profit_loss': float(row['total_profit_loss']),
            'average_profit_loss': float(row['average_profit_loss']),
            'win_rate': float(row['win_rate'])
        })
    
    logger.info(f"Calculated {len(metrics)} temporal performance records")
    return metrics


def insert_temporal_performance(conn: sqlite3.Connection, metrics: List[Dict]) -> None:
    """Insert calculated metrics into temporal_performance table."""
    logger.info("Inserting temporal performance data...")
    
    cursor = conn.cursor()
    
    insert_query = """
    INSERT INTO temporal_performance (
        account_name, base_symbol, hour_of_day, day_of_week,
        total_trades, winning_trades, total_profit_loss,
        average_profit_loss, win_rate, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    current_time = datetime.now().isoformat()
    
    for metric in metrics:
        cursor.execute(insert_query, (
            metric['account_name'],
            metric['base_symbol'],
            metric['hour_of_day'],
            metric['day_of_week'],
            metric['total_trades'],
            metric['winning_trades'],
            metric['total_profit_loss'],
            metric['average_profit_loss'],
            metric['win_rate'],
            current_time,
            current_time
        ))
    
    conn.commit()
    logger.info(f"Inserted {len(metrics)} temporal performance records")


def get_summary_stats(conn: sqlite3.Connection) -> Dict:
    """Get summary statistics after population."""
    cursor = conn.cursor()
    
    # Count records in temporal_performance
    cursor.execute("SELECT COUNT(*) as count FROM temporal_performance")
    temporal_count = cursor.fetchone()['count']
    
    # Count unique accounts
    cursor.execute("SELECT COUNT(DISTINCT account_name) as count FROM temporal_performance")
    unique_accounts = cursor.fetchone()['count']
    
    # Count unique symbols
    cursor.execute("SELECT COUNT(DISTINCT base_symbol) as count FROM temporal_performance")
    unique_symbols = cursor.fetchone()['count']
    
    # Get sample of best performing combinations
    cursor.execute("""
        SELECT account_name, base_symbol, hour_of_day, day_of_week, 
               total_trades, average_profit_loss, win_rate
        FROM temporal_performance 
        WHERE average_profit_loss > 0
        ORDER BY average_profit_loss DESC 
        LIMIT 5
    """)
    top_performers = cursor.fetchall()
    
    return {
        'total_records': temporal_count,
        'unique_accounts': unique_accounts,
        'unique_symbols': unique_symbols,
        'top_performers': [dict(row) for row in top_performers]
    }


def main():
    """Main execution function."""
    logger.info("Starting temporal performance population process...")
    
    try:
        # Connect to database
        conn = get_database_connection()
        logger.info("Database connection established")
        
        # Clear existing data
        clear_temporal_performance_table(conn)
        
        # Calculate metrics
        metrics = calculate_temporal_metrics(conn)
        
        if not metrics:
            logger.warning("No temporal metrics calculated - check if processed_trades has data")
            return
        
        # Insert metrics
        insert_temporal_performance(conn, metrics)
        
        # Get summary
        summary = get_summary_stats(conn)
        
        logger.info("=== POPULATION COMPLETE ===")
        logger.info(f"Total records inserted: {summary['total_records']}")
        logger.info(f"Unique accounts: {summary['unique_accounts']}")
        logger.info(f"Unique symbols: {summary['unique_symbols']}")
        
        if summary['top_performers']:
            logger.info("Top 5 performing combinations:")
            for i, perf in enumerate(summary['top_performers'], 1):
                logger.info(f"  {i}. {perf['account_name']} ({perf['base_symbol']}) - "
                          f"Hour {perf['hour_of_day']}, Day {perf['day_of_week']} - "
                          f"Avg P&L: ${perf['average_profit_loss']:.2f}, "
                          f"Win Rate: {perf['win_rate']:.1f}%")
        
        conn.close()
        logger.info("Process completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during population: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()