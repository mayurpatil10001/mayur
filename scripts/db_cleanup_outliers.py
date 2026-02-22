import sqlite3
from trading_platform.services.binary_log_parser import BinaryLogParser

def cleanup_database():
    print("Starting database cleanup for outliers...")
    parser = BinaryLogParser("trading_platform.db")
    
    # purge_anomalies(account=None) processes all accounts in the DB
    # and applies the newly implemented statistical outlier logic.
    breakdown = parser.purge_anomalies(account=None, purge_overnight=True)
    
    total_outliers = 0
    total_pnl_removed = 0.0
    
    print("\nCleanup Breakdown:")
    print("-" * 50)
    for acc, stats in breakdown.items():
        outlier_stats = stats.get("outliers", {})
        count = outlier_stats.get("count", 0)
        pnl = outlier_stats.get("pnl", 0.0)
        
        if count > 0:
            print(f"Account: {acc:<15} | Outliers Removed: {count:<3} | PnL Impact: ${pnl:>10.2f}")
            total_outliers += count
            total_pnl_removed += pnl
    
    print("-" * 50)
    print(f"Total Outliers Removed: {total_outliers}")
    print(f"Total PnL Impact: ${total_pnl_removed:.2f}")
    print("Cleanup complete.")

if __name__ == "__main__":
    cleanup_database()
