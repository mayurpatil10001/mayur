import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Checking trades for V_sim16 in 2026-02-24...")
# Try exact date match or LIKE
cursor.execute("SELECT id, account, symbol, entry_time, net_profit FROM trades WHERE account = 'V_sim16' AND entry_time LIKE '2026-02-24%' ORDER BY entry_time DESC")
rows = cursor.fetchall()
if not rows:
    print("No trades found for V_sim16 on 2026-02-24.")
    print("Checking if any trades at all for 2026-02-24...")
    cursor.execute("SELECT count(*), account FROM trades WHERE entry_time LIKE '2026-02-24%' GROUP BY account")
    for r in cursor.fetchall():
        print(r)
else:
    for r in rows:
        print(r)

print("\nLast 5 trades overall for ANY account:")
cursor.execute("SELECT id, account, symbol, entry_time FROM trades ORDER BY id DESC LIMIT 5")
for r in cursor.fetchall():
    print(r)

conn.close()
