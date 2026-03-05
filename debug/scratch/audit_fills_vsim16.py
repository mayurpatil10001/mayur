import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- FULL POSITION_STATE TABLE ---")
c.execute("SELECT * FROM position_state")
for row in c.fetchall():
    print(dict(row))

print("\n--- FILLS FOR V_SIM16 ON DEC 18 ---")
# Check if there are any fills for V_SIM16 on Dec 18
# We need to know where these fills are coming from.
c.execute("""
    SELECT entry_time, side, quantity, price, type, message 
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
""")
for row in c.fetchall():
    print(dict(row))

# Also check processed_trades for ANY trades on Dec 18 before 07:00
print("\n--- PROCESSED TRADES FOR V_SIM16 ON DEC 18 (EARLY) ---")
c.execute("""
    SELECT entry_time, exit_time, side, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
      AND entry_time < '2025-12-18T07:00:00'
    ORDER BY entry_time ASC
""")
for r in c.fetchall():
    print(f"  {r['entry_time']} | {r['exit_time']} | {r['side']} | {r['quantity']} | ${r['profit_loss']}")

conn.close()
