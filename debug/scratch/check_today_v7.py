import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Trades with EXIT_TIME on 2026-02-24:")
cursor.execute("""
    SELECT entry_time, exit_time, symbol, side, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND exit_time >= '2026-02-24T00:00:00'
    ORDER BY exit_time DESC
""")
rows = cursor.fetchall()
print(f"Total: {len(rows)}")
for r in rows[:10]:
    print(dict(r))

conn.close()
