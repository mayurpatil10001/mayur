import sqlite3
import os

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(db_path)
try:
    c = conn.cursor()
    c.execute("DELETE FROM processed_trades;")
    conn.commit()
    print("Database cleared successfully.")
except Exception as e:
    print(f"Error clearing database: {e}")
finally:
    conn.close()
