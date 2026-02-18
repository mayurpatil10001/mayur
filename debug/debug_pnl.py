import sqlite3

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT * FROM processed_trades WHERE entry_time = '2024-05-24T08:03:44'")
row = c.fetchone()
print(row)

# Let's also check the 2024-05 totals again
c.execute("SELECT SUM(profit_loss), COUNT(*) FROM processed_trades WHERE account_name = 'CL-TS_4'")
print(f"Total CL-TS_4: {c.fetchone()}")

conn.close()
