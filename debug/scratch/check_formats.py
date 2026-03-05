import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("--- SAMPLE PENDING FILLS (Last 10) ---")
c.execute("SELECT entry_time, account_name FROM pending_fills ORDER BY entry_time DESC LIMIT 10")
for row in c.fetchall():
    print(dict(row))

print("\n--- PROCESSED TRADES FOR V_SIM16 (ANY DATE) ---")
c.execute("SELECT entry_time, side, quantity FROM processed_trades WHERE account_name = 'V_SIM16' LIMIT 5")
for row in c.fetchall():
    print(dict(row))

conn.close()
