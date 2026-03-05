import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- TARGETED CHECK FOR 02:33 UTC TRADE ---")
c.execute("""
    SELECT trade_id, entry_time, exit_time, side, quantity, profit_loss
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
      AND (entry_time LIKE '%T02:33%' OR exit_time LIKE '%T02:45%')
""")
rows = c.fetchall()
if not rows:
    print("MATCHING TRADE NOT FOUND IN DB!")
else:
    for row in rows:
        print(dict(row))

print("\n--- FIRST 20 TRADES ON DEC 18 FOR V_SIM16 ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
    LIMIT 20
""")
for row in c.fetchall():
    print(dict(row))

conn.close()
