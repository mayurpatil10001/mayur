import sqlite3
import datetime

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Show last 100 trades by entry_time:")
cursor.execute("SELECT entry_time, exit_time, account_name, symbol, profit_loss FROM processed_trades ORDER BY entry_time DESC LIMIT 100")
for r in cursor.fetchall():
    print(dict(r))

print("\nShow last 100 trades by exit_time:")
cursor.execute("SELECT entry_time, exit_time, account_name, symbol, profit_loss FROM processed_trades ORDER BY exit_time DESC LIMIT 100")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
