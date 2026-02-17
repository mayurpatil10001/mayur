
import sqlite3
import time

def optimized_cleanup():
    conn = sqlite3.connect('trading_platform.db')
    cursor = conn.cursor()
    
    print("Starting optimized cleanup...")
    
    # Check total records first
    cursor.execute("SELECT COUNT(*) FROM processed_trades")
    total_before = cursor.fetchone()[0]
    print(f"Total records before: {total_before}")

    # Index trade_id if it's not indexed
    try:
        print("Creating index on trade_id...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_id ON processed_trades(trade_id)")
        print("Creating index on symbol...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON processed_trades(symbol)")
        conn.commit()
    except:
        pass

    # Delete in batches to avoid huge locks and show progress
    def delete_in_batches(where_clause, description):
        print(f"Deleting {description}...")
        while True:
            cursor.execute(f"DELETE FROM processed_trades WHERE trade_id IN (SELECT trade_id FROM processed_trades WHERE {where_clause} LIMIT 100000)")
            deleted = cursor.rowcount
            conn.commit()
            print(f"  Deleted {deleted} records...")
            if deleted < 100000:
                break

    delete_in_batches("trade_id LIKE 'BIN_%'", "BIN_ records")
    delete_in_batches("symbol = 'Unknown'", "Unknown symbols")
    delete_in_batches("symbol = 'T'", "symbol T")
    delete_in_batches("symbol = 'Tsufim'", "symbol Tsufim")
    delete_in_batches("symbol LIKE 'V_%'", "symbol V_")
    delete_in_batches("entry_time > '2026-03-01'", "future dates")

    print("Reclaiming disk space (VACUUM)...")
    conn.execute("VACUUM")
    
    cursor.execute("SELECT COUNT(*) FROM processed_trades")
    total_after = cursor.fetchone()[0]
    print(f"Total records after: {total_after}")
    
    conn.close()
    print("Cleanup finished.")

if __name__ == '__main__':
    optimized_cleanup()
