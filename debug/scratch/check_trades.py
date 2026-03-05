import sqlite3
import json

db_path = "trading_platform.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

account = 'V_SIM16'
date = '2025-11-05'

c.execute("""
    SELECT entry_time, side, quantity, entry_price, profit_loss as pnl
    FROM processed_trades 
    WHERE account_name = ? COLLATE NOCASE AND date(entry_time) = ?
    ORDER BY entry_time ASC
    LIMIT 20
""", (account, date))

rows = [dict(r) for r in c.fetchall()]
print(json.dumps(rows, indent=2))
conn.close()
