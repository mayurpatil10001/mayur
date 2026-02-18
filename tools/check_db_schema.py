import sqlite3
import os

db_path = 'trading_platform.db'
if not os.path.exists(db_path):
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(processed_trades)")
    cols = cursor.fetchall()
    for col in cols:
        print(f"ID: {col[0]}, Name: {col[1]}, Type: {col[2]}")
    conn.close()
