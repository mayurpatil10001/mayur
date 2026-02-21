
import sqlite3
import os

db_path = 'trading_platform.db'
if not os.path.exists(db_path):
    print("DB not found")
    exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

try:
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='market_data'")
    print(f"Schema: {c.fetchone()}")
    
    # Check column names
    c.execute("PRAGMA table_info(market_data)")
    cols = c.fetchall()
    print(f"Columns: {cols}")
    
    # Check a few rows
    c.execute("SELECT date FROM market_data LIMIT 5")
    print(f"Sample dates: {c.fetchall()}")
    
    # Try the update again with a more robust query
    c.execute("UPDATE market_data SET date = substr(date, 1, 10) WHERE length(date) > 10")
    print(f"Updated {c.rowcount} rows")
    
    conn.commit()
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
