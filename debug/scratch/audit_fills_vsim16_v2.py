import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Check schema of pending_fills
print("--- SCHEMA OF pending_fills ---")
c.execute("PRAGMA table_info(pending_fills)")
for col in c.fetchall():
    print(dict(col))

# Re-run the audit with correct column names (guessing 'side' is there, but maybe not 'type')
print("\n--- FILLS FOR V_SIM16 ON DEC 18 ---")
c.execute("""
    SELECT entry_time, side, quantity, price, message 
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
""")
for row in c.fetchall():
    print(dict(row))

conn.close()
