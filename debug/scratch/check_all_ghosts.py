import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Accounts with high pending fill quantity (> 100):")
cursor.execute("SELECT account_name, symbol, side, sum(quantity) as total_qty FROM pending_fills GROUP BY account_name, symbol, side HAVING sum(quantity) > 100")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
