import os
import sqlite3

def check_db_lock():
    db_file = 'trading_platform.db'
    wal_file = db_file + '-wal'
    
    print(f"Checking {db_file}...")
    try:
        # Try to open in exclusive mode
        conn = sqlite3.connect(db_file, timeout=1)
        # Try a write operation (dummy)
        conn.execute("CREATE TABLE IF NOT EXISTS _lock_test (internal integer)")
        conn.execute("DROP TABLE _lock_test")
        conn.commit()
        conn.close()
        print("Success: Database is NOT locked by another process.")
    except sqlite3.OperationalError as e:
        print(f"OperationalError: {e}")
        if "database is locked" in str(e).lower():
            print("CRITICAL: Database is LOCKED.")
    except Exception as e:
        print(f"Other Error: {e}")

if __name__ == "__main__":
    check_db_lock()
