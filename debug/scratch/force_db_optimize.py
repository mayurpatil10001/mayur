import sqlite3
import os
import time

DB = "trading_platform.db"
WAL = DB + "-wal"
SHM = DB + "-shm"

def force_optimize():
    print(f"Starting offline optimization for {DB}...")
    if os.path.exists(DB):
        try:
            conn = sqlite3.connect(DB)
            # Switch to DELETE mode temporarily to merge WAL
            print("Switching to journal_mode=DELETE to merge WAL...")
            conn.execute("PRAGMA journal_mode=DELETE")
            print("Vacuuming database...")
            start = time.time()
            conn.execute("VACUUM")
            conn.commit()
            print(f"Vacuum complete in {time.time()-start:.2f}s")
            
            # Switch back to WAL for performance
            print("Switching back to journal_mode=WAL...")
            conn.execute("PRAGMA journal_mode=WAL")
            conn.close()
            
            # Cleanup files if they still exist
            for f in [WAL, SHM]:
                if os.path.exists(f):
                    os.remove(f)
                    print(f"Removed {f}")
            
            print("Optimization successful.")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Database not found.")

if __name__ == "__main__":
    force_optimize()
