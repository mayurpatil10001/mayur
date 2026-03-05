import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- FILLS COUNT FOR V_SIM16 ON DEC 18 ---")
c.execute("""
    SELECT count(*) as cnt 
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
""")
print(dict(c.fetchone()))

print("\n--- GHOST FILLS COUNT FOR V_SIM16 ON DEC 18 ---")
c.execute("""
    SELECT count(*) as cnt 
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
      AND is_ghost = 1
""")
print(dict(c.fetchone()))

print("\n--- EARLY FILLS FOR V_SIM16 ON DEC 18 (Sorted) ---")
c.execute("""
    SELECT entry_time, side, quantity, price, is_ghost
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
    LIMIT 20
""")
for row in c.fetchall():
    print(dict(row))

conn.close()
