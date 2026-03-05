import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

print("Case in pending_fills:")
res1 = conn.execute("SELECT count(*) FROM pending_fills WHERE account_name = 'V_sim16'").fetchone()[0]
res2 = conn.execute("SELECT count(*) FROM pending_fills WHERE account_name = 'V_SIM16'").fetchone()[0]

print(f"Count 'V_sim16': {res1}")
print(f"Count 'V_SIM16': {res2}")

conn.close()
