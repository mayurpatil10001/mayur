import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Net Position in Pending Fills for V_sim16:")
cursor.execute("SELECT side, sum(quantity) as total_qty FROM pending_fills WHERE account_name = 'V_sim16' GROUP BY side")
for r in cursor.fetchall():
    print(dict(r))

conn.close()
