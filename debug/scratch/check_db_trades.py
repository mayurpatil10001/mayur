import sqlite3
import os

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking trades for V_sim16 for 2026-02-24...")
cursor.execute("SELECT count(*), account_name, symbol, entry_time FROM trades WHERE account_name = 'V_sim16' AND entry_time LIKE '2026-02-24%' GROUP BY account_name, symbol")
rows = cursor.fetchall()
for r in rows:
    print(r)

print("\nChecking last 5 trades for V_sim16 overall:")
cursor.execute("SELECT entry_time, exit_time, symbol, profit_loss FROM trades WHERE account_name = 'V_sim16' ORDER BY entry_time DESC LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(r)

conn.close()
