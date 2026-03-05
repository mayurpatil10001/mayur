import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Full check for V_sim16:")
cursor.execute("SELECT id, symbol, entry_time, net_profit FROM processed_trades WHERE account_name = 'V_sim16' ORDER BY entry_time DESC LIMIT 20")
rows = cursor.fetchall()
if not rows:
    print("No V_sim16 trades found in processed_trades.")
else:
    for r in rows:
        print(r)

conn.close()
