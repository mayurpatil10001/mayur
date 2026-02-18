
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
print("--- Daily Trade Counts for 3Q_sim14 ---")
c.execute("""
    SELECT substr(entry_time, 1, 10) as day, COUNT(*) 
    FROM processed_trades 
    WHERE account_name = '3Q_SIM14' 
    GROUP BY day 
    ORDER BY day DESC
    LIMIT 30
""")
for day, count in c.fetchall():
    print(f"{day}: {count} trades")
conn.close()
