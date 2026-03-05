import sqlite3
from datetime import datetime

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- EARLIEST 10 TRADES FOR V_SIM16 (120-Day Import) ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
    ORDER BY entry_time ASC 
    LIMIT 10
""")
for r in c.fetchall():
    print(f"  {r['entry_time']} | {r['exit_time']} | {r['side']} | {r['quantity']} | ${r['profit_loss']}")

print("\n--- DEC 18 TRADES FOR V_SIM16 ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
""")
for r in c.fetchall():
    print(f"  {r['entry_time']} | {r['exit_time']} | {r['side']} | {r['quantity']} | ${r['profit_loss']}")

conn.close()
