import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Current Pending Fills Summary for V_SIM16:")
cursor.execute("SELECT side, sum(quantity) as total_qty FROM pending_fills WHERE account_name = 'V_SIM16' GROUP BY side")
for r in cursor.fetchall():
    print(dict(r))

print("\nLast 10 pending fills for V_SIM16:")
cursor.execute("SELECT * FROM pending_fills WHERE account_name = 'V_SIM16' ORDER BY entry_time DESC LIMIT 10")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
