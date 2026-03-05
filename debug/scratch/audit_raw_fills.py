import sqlite3

conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
query = "SELECT timestamp, side, quantity, price FROM raw_fills WHERE account_name = 'V_SIM16' AND timestamp LIKE '2025-12-18T07:26%'"
c.execute(query)
rows = c.fetchall()

print("--- RAW FILLS 07:26 UTC (Dec 18) ---")
for r in rows:
    print(r)
conn.close()
