import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- ALL SIM13 TRADES IN LAST 2 DAYS ---")
c.execute("""
    SELECT entry_time, exit_time, symbol, profit_loss 
    FROM processed_trades 
    WHERE account_name = '3Q_SIM13' 
    AND entry_time > date('now', '-2 days')
    ORDER BY entry_time DESC
""")
rows = c.fetchall()
print(f"Found {len(rows)} trades.")
for row in rows:
    print(row)

conn.close()
