import sqlite3
import pprint

conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

c.execute("PRAGMA table_info(processed_trades)")
print(c.fetchall())

c.execute("SELECT datetime, side, quantity, price, order_id FROM processed_trades WHERE account_name='V_SIM16' AND datetime LIKE '2026-02-25 03:00%' ORDER BY datetime")
rows = c.fetchall()

print(f"Total rows found: {len(rows)}")
for r in rows:
    print(r)
