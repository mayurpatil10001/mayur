import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- SAMPLE RECORD FROM pending_fills ---")
c.execute("SELECT * FROM pending_fills LIMIT 1")
row = c.fetchone()
if row:
    print(dict(row))
else:
    print("Table is empty.")

print("\n--- SCHEMA OF pending_fills (DETAIL) ---")
c.execute("PRAGMA table_info(pending_fills)")
for col in c.fetchall():
    print(dict(col))

# Now try to find the 02:26 fills
print("\n--- FILLS FOR V_SIM16 ON DEC 18 (02:20 - 02:30) ---")
# Use the correct column names from the schema check
c.execute("""
    SELECT * 
    FROM pending_fills 
    WHERE account_name = 'V_SIM16' COLLATE NOCASE 
      AND entry_time >= '2025-12-18T02:20:00'
      AND entry_time <= '2025-12-18T02:30:00'
    ORDER BY entry_time ASC
""")
for row in c.fetchall():
    print(dict(row))

conn.close()
