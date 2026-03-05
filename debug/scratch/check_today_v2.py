import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking for trades with entry_time on 2026-02-24:")
cursor.execute("SELECT count(*), account_name, symbol FROM processed_trades WHERE entry_time LIKE '2026-02-24%' GROUP BY account_name, symbol")
for r in cursor.fetchall():
    print(r)

print("\nChecking for trades with exit_time on 2026-02-24:")
cursor.execute("SELECT count(*), account_name, symbol FROM processed_trades WHERE exit_time LIKE '2026-02-24%' GROUP BY account_name, symbol")
for r in cursor.fetchall():
    print(r)

conn.close()
