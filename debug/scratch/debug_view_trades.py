import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Top 20 trades for V_SIM16 with Filter >= 2026-02-24:")
cursor.execute("""
    SELECT entry_time, exit_time, symbol, side, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND (entry_time >= '2026-02-24T00:00:00' OR exit_time >= '2026-02-24T00:00:00')
    ORDER BY entry_time DESC 
    LIMIT 20
""")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
