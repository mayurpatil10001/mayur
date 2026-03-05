import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- FULL SWEEP FOR V_SIM16 ON 2025-12-18 (UTF) ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
""")
rows = c.fetchall()
if not rows:
    print("NO TRADES FOUND FOR DEC 18!")
else:
    for row in rows:
        print(f"{row['entry_time']} | {row['exit_time']} | {row['side']} | {row['quantity']} | {row['profit_loss']:.2f}")

conn.close()
