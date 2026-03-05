import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Resetting Ghost Position for V_SIM16...")
cursor.execute("DELETE FROM pending_fills WHERE account_name = 'V_SIM16' COLLATE NOCASE")
print(f"Deleted {cursor.rowcount} pending executions.")

conn.commit()
conn.close()
print("State reset complete.")
