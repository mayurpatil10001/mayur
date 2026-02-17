import sqlite3
import os

db_path = 'trading_platform.db'
if not os.path.exists(db_path):
    print("DB not found")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT account_name, symbol, COUNT(*) FROM processed_trades GROUP BY account_name, symbol LIMIT 20")
    rows = cursor.fetchall()
    for row in rows:
        print(f"Account: {row[0]}, Symbol: {row[1]}, Count: {row[2]}")
    conn.close()
