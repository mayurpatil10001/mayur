import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT COUNT(*), MAX(exit_time) FROM processed_trades WHERE account_name = '3Q_SIM13'")
res = c.fetchone()
print(f"Total SIM13 trades: {res[0]}")
print(f"Last SIM13 trade: {res[1]}")

conn.close()
