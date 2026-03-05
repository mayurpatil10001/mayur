import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

print("Accounts in processed_trades:")
cursor = conn.execute("SELECT DISTINCT account_name FROM processed_trades")
for r in cursor.fetchall():
    print(r[0])

print("\nAccounts in pending_fills:")
cursor = conn.execute("SELECT DISTINCT account_name FROM pending_fills")
for r in cursor.fetchall():
    print(r[0])

conn.close()
