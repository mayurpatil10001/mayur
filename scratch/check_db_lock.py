import sqlite3
import time

try:
    print("Checking database access...")
    conn = sqlite3.connect("trading_platform.db", timeout=5)
    cursor = conn.cursor()
    cursor.execute("SELECT count(*) FROM processed_trades")
    print(f"Trade count: {cursor.fetchone()[0]}")
    conn.close()
    print("Database is accessible.")
except Exception as e:
    print(f"Error accessing database: {e}")
