import sqlite3
import os

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

account = "V_SIM16"
day = "2025-12-01"

c.execute("""
    SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss 
    FROM processed_trades 
    WHERE account_name = ? AND date(entry_time) = ?
    ORDER BY entry_time ASC LIMIT 20
""", (account, day))

rows = c.fetchall()
print(f"--- SAMPLE TRADES FOR {account} on {day} ---")
for r in rows:
    print(f"{r['entry_time']} | {r['side']} | Qty: {r['quantity']} | {r['entry_price']} -> {r['exit_price']} | PnL: {r['profit_loss']}")

conn.close()
