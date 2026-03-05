import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Trades ENTERING today (2026-02-24):")
cursor.execute("SELECT count(*) FROM processed_trades WHERE entry_time LIKE '2026-02-24%'")
count = cursor.fetchone()[0]
print(f"Total: {count}")

cursor.execute("SELECT entry_time, exit_time, account_name, symbol FROM processed_trades WHERE entry_time LIKE '2026-02-24%' LIMIT 10")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
