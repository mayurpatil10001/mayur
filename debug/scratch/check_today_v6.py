import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

res = conn.execute("SELECT count(*) FROM processed_trades WHERE entry_time LIKE '2026-02-19%' AND exit_time LIKE '2026-02-24%'").fetchone()[0]
print(f"Total 4.5 day swing trades (Feb 19 -> Feb 24): {res}")

conn.close()
