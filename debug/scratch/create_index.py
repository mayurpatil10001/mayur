import sqlite3
import os

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'

print(f"Connecting to {db_path}...")
try:
    conn = sqlite3.connect(db_path)
    print("Creating index on entry_time (this may take a minute with 675k rows)...")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON processed_trades(entry_time);')
    conn.commit()
    conn.close()
    print("SUCCESS: Index created on processed_trades(entry_time).")
except Exception as e:
    print(f"ERROR: {str(e)}")
