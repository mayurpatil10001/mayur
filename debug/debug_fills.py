import sqlite3
import os
import datetime

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- ALL FILLS FOR SIM13 IN LAST 10 DAYS ---")
cutoff = (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()
# Try generic query first
c.execute("SELECT timestamp, symbol, side, quantity, price FROM fills WHERE account_name = '3Q_SIM13' ORDER BY timestamp DESC LIMIT 20")
rows = c.fetchall()
print(f"Total fills found: {len(rows)}")
for row in rows:
    print(row)

conn.close()
