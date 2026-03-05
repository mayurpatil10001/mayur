import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Trade counts by year:")
cursor.execute("SELECT substr(entry_time, 1, 4) as year, count(*) FROM processed_trades GROUP BY year")
for r in cursor.fetchall():
    print(r)

print("\nLast 10 trades by entry_time (any year):")
cursor.execute("SELECT entry_time, account_name, symbol FROM processed_trades ORDER BY entry_time DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

conn.close()
