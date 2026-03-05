import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Duration of trades exiting today:")
cursor.execute("SELECT trade_id, entry_time, exit_time, duration_minutes FROM processed_trades WHERE exit_time LIKE '2026-02-24%' LIMIT 10")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
