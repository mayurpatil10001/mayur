import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking trades for V_sim16 in 2026...")
cursor.execute("SELECT count(*), account, symbol FROM trades WHERE account = 'V_sim16' AND entry_time LIKE '2026%' GROUP BY account, symbol")
rows = cursor.fetchall()
for r in rows:
    print(r)

print("\nLast 10 trades for V_sim16 overall (by id desc):")
cursor.execute("SELECT id, account, symbol, entry_time, profit_loss FROM trades WHERE account = 'V_sim16' ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()
for r in rows:
    print(r)

conn.close()
