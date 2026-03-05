import os
import sqlite3

db_file = "trading_platform.db"

print("--- HARD RESET INITIATED ---")

if os.path.exists(db_file):
    print(f"Closing connections and deleting {db_file}...")
    try:
        # We try to connect and close just to be sure, though os.remove is what matters
        if os.path.exists(db_file + "-wal"): os.remove(db_file + "-wal")
        if os.path.exists(db_file + "-shm"): os.remove(db_file + "-shm")
        os.remove(db_file)
        print("✅ Database file deleted successfully.")
    except Exception as e:
        print(f"❌ Error deleting file: {e}")
        print("Make sure the Backend (Nitro Engine) is STOPPED before wiping!")
else:
    print("ℹ️ Database file not found. Nothing to wipe.")

print("\nSuccess! The system will recreate a clean database on next startup.")
