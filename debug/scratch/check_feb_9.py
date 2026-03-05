import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Checking trades from 2026-02-09 that might be matching the filter:")
cursor.execute("""
    SELECT entry_time, exit_time, symbol, side, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND entry_time LIKE '2026-02-09%'
    ORDER BY exit_time DESC
    LIMIT 10
""")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
