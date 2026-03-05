import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT min(entry_time), max(entry_time), count(*) FROM processed_trades WHERE account_name = 'V_SIM16'")
res = cursor.fetchone()
print(f"V_SIM16 Range: {res[0]} to {res[1]} (Total: {res[2]})")

conn.close()
