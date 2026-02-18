import sqlite3
import os

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT DISTINCT account_name FROM processed_trades")
accounts = [r[0] for r in c.fetchall()]
print(f"Accounts in DB: {accounts}")

conn.close()
