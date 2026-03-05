import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

res = conn.execute("SELECT count(*) FROM processed_trades WHERE account_name = 'V_SIM16' AND exit_time LIKE '2026-02-24%'").fetchone()[0]
print(f"Total V_SIM16 trades exiting today: {res}")

conn.close()
