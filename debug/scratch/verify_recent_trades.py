import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Verifying most recent trades for V_SIM16 in DB:")
cursor.execute("""
    SELECT entry_time, exit_time, symbol, side, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
    ORDER BY entry_time DESC 
    LIMIT 20
""")
for r in cursor.fetchall():
    print(dict(r))

print("\nCounting trades on 2026-02-24 specifically:")
cursor.execute("""
    SELECT count(*) 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND (entry_time LIKE '2026-02-24%' OR exit_time LIKE '2026-02-24%')
""")
print(f"Total for 2026-02-24: {cursor.fetchone()[0]}")

conn.close()
