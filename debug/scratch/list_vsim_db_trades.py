import sqlite3
import datetime

conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

print("V_SIM16 Trades on Dec 18 (from processed_trades):")
c.execute("""
    SELECT entry_time, exit_time, quantity, entry_price, exit_price, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
    AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time
""")

rows = c.fetchall()
for r in rows:
    print(r)

conn.close()
