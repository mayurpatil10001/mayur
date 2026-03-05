import sqlite3
import os

DB = "trading_platform.db"

def checkpoint():
    print(f"Opening {DB} for WAL checkpoint...")
    try:
        conn = sqlite3.connect(DB)
        c = conn.cursor()
        print("Running PRAGMA wal_checkpoint(TRUNCATE)...")
        c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print("Checkpoint complete.")
        conn.close()
    except Exception as e:
        print(f"Error during checkpoint: {e}")

if __name__ == "__main__":
    checkpoint()
    # Check sizes after
    for f in [DB, f"{DB}-wal", f"{DB}-shm"]:
        if os.path.exists(f):
            size = os.path.getsize(f)
            print(f"{f}: {size:,} bytes")
