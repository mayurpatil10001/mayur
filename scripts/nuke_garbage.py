
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

    # 1. Delete all records from the binary import (the ones I just did)
    # These all start with 'BIN_'
    print("Deleting BIN_ records...")
    cursor.execute("DELETE FROM processed_trades WHERE trade_id LIKE 'BIN_%'")
    print(f"Deleted {cursor.rowcount} BIN_ records.")
    conn.commit()

    # 2. Delete other obviously wrong symbols that might have been there before
    bad_symbols = ['Unknown', 'T', 'Tsufim']
    for sym in bad_symbols:
        print(f"Deleting symbol {sym}...")
        cursor.execute("DELETE FROM processed_trades WHERE symbol = ?", (sym,))
        print(f"Deleted {cursor.rowcount} {sym} records.")
        conn.commit()

    # 3. Future dates
    print("Deleting future dates...")
    cursor.execute("DELETE FROM processed_trades WHERE entry_time > '2026-03-01'")
    print(f"Deleted {cursor.rowcount} future date records.")
    conn.commit()

    # VACUUM to reclaim space since we deleted millions of rows
    print("Reclaiming disk space (VACUUM)... This might take a minute.")
    conn.execute("VACUUM")
    
    cursor.execute("SELECT COUNT(*) FROM processed_trades")
    total_after = cursor.fetchone()[0]
    print(f"Total records after: {total_after}")
    
    conn.close()
    print("Cleanup finished.")

if __name__ == '__main__':
    optimized_cleanup()
