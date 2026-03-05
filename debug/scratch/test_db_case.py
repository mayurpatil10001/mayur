import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

print("Testing case sensitivity:")
res1 = conn.execute("SELECT count(*) FROM processed_trades WHERE account_name = 'V_sim16'").fetchone()[0]
res2 = conn.execute("SELECT count(*) FROM processed_trades WHERE account_name = 'V_SIM16'").fetchone()[0]
res3 = conn.execute("SELECT count(*) FROM processed_trades WHERE account_name = 'V_sim16' COLLATE NOCASE").fetchone()[0]

print(f"Count 'V_sim16': {res1}")
print(f"Count 'V_SIM16': {res2}")
print(f"Count 'V_sim16' NOCASE: {res3}")

conn.close()
