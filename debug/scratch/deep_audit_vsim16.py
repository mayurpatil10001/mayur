import sqlite3
from datetime import datetime

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- V_SIM16 PERFORMANCE SUMMARY SINCE INCEPTION (120 Days) ---")
c.execute("""
    SELECT side, count(*) as cnt, sum(profit_loss) as total_pnl
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
    GROUP BY side
""")
for r in c.fetchall():
    print(f"  {r['side']}: {r['cnt']} trades, PnL=${r['total_pnl']}")

print("\n--- TRADES BEFORE DEC 18 (Last 10) ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time < '2025-12-18'
    ORDER BY entry_time DESC
    LIMIT 10
""")
for r in c.fetchall():
    print(f"  {r['entry_time']} | {r['exit_time']} | {r['side']} | {r['quantity']} | ${r['profit_loss']}")

print("\n--- DEC 18 TRADES (FULL LIST) ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
""")
for r in c.fetchall():
    print(f"  {r['entry_time']} | {r['exit_time']} | {r['side']} | {r['quantity']} | ${r['profit_loss']}")

print("\n--- PENDING STATE AT THE END OF DEC 17 ---")
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='position_state'")
if c.fetchone():
    c.execute("SELECT * FROM position_state WHERE account_name = 'V_SIM16' COLLATE NOCASE")
    rows = c.fetchall()
    for row in rows:
        print(dict(row))
else:
    print("Table position_state does NOT exist.")

conn.close()
