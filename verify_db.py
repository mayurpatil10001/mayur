import sqlite3
import os

db_file = 'trading_platform.db'
print(f"Checking DB file: {os.path.abspath(db_file)}")
print(f"Size: {os.path.getsize(db_file)} bytes")

conn = sqlite3.connect(db_file)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(f"Tables: {cur.fetchall()}")

cur.execute("SELECT COUNT(*) FROM processed_trades")
print(f"Raw count in processed_trades: {cur.fetchone()[0]}")

cur.execute("SELECT DISTINCT account_name FROM processed_trades LIMIT 5")
print(f"Accounts: {cur.fetchall()}")

conn.close()
