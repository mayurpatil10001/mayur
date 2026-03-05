import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Trade counts by entry day (last 10 days):")
cursor.execute("""
    SELECT substr(entry_time, 1, 10) as day, count(*) 
    FROM processed_trades 
    GROUP BY day 
    ORDER BY day DESC 
    LIMIT 10
""")
for r in cursor.fetchall():
    print(r)

print("\nRecent 10 trades details:")
cursor.execute("""
    SELECT trade_id, account_name, symbol, entry_time, exit_time, profit_loss 
    FROM processed_trades 
    ORDER BY entry_time DESC 
    LIMIT 10
""")
for r in cursor.fetchall():
    print(r)

conn.close()
