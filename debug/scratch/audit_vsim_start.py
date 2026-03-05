import sqlite3

conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
query = "SELECT entry_time, exit_time, side, quantity, profit_loss FROM processed_trades WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12-18%' ORDER BY entry_time ASC LIMIT 20"
c.execute(query)
rows = c.fetchall()

print("--- DEC 18 START (V_SIM16) ---")
for r in rows:
    print(r)
conn.close()
