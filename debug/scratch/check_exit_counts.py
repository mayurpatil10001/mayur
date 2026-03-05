import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Trade counts by EXIT day (last 10 days):")
cursor.execute("""
    SELECT substr(exit_time, 1, 10) as day, count(*) 
    FROM processed_trades 
    GROUP BY day 
    ORDER BY day DESC 
    LIMIT 10
""")
for r in cursor.fetchall():
    print(r)

conn.close()
