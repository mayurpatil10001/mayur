import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking tables in DB:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
for t in cursor.fetchall():
    print(t)

print("\nChecking processed_trades for V_sim16 in 2026-02-24...")
try:
    cursor.execute("SELECT count(*), account_name, symbol FROM processed_trades WHERE account_name = 'V_sim16' AND entry_time LIKE '2026-02-24%' GROUP BY account_name, symbol")
    for r in cursor.fetchall():
        print(r)
except Exception as e:
    print(f"Error checking processed_trades: {e}")

conn.close()
