import sqlite3
import os

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("--- PENDING FILLS (Last 10) ---")
cursor.execute("SELECT * FROM pending_fills ORDER BY created_at DESC LIMIT 10")
rows = cursor.fetchall()
for r in rows:
    print(dict(r))

print("\n--- PROCESSED TRADES (Last 5) ---")
cursor.execute("SELECT * FROM processed_trades ORDER BY entry_time DESC LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(dict(r))

conn.close()
