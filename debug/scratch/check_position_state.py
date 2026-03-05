import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- POSITION STATE FOR V_SIM16 ---")
c.execute("SELECT * FROM position_state WHERE account_name = 'V_SIM16' COLLATE NOCASE")
for row in c.fetchall():
    print(dict(row))

print("\n--- PENDING FILLS FOR V_SIM16 ---")
c.execute("SELECT * FROM pending_fills WHERE account_name = 'V_SIM16' COLLATE NOCASE LIMIT 10")
for row in c.fetchall():
    print(dict(row))

conn.close()
