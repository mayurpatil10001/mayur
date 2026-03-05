import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- TRADES EXITING ON DEC 18 FOR V_SIM16 ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND exit_time LIKE '2025-12-18%'
    ORDER BY exit_time ASC
    LIMIT 20
""")
for row in c.fetchall():
    print(dict(row))

print("\n--- PENDING STATE AFTER DEC 17 ---")
c.execute("""
    SELECT * FROM position_state WHERE account_name = 'V_SIM16' COLLATE NOCASE
""")
for row in c.fetchall():
    print(dict(row))

conn.close()
