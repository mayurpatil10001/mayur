import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking last 10 processed_trades symbols and account names:")
cursor.execute("SELECT trade_id, account_name, symbol, entry_time FROM processed_trades ORDER BY entry_time DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

conn.close()
