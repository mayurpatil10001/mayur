
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("SELECT symbol, account_name FROM processed_trades LIMIT 20")
print(f"Sample trades: {c.fetchall()}")
c.execute("SELECT COUNT(*) FROM processed_trades WHERE symbol LIKE 'NQ%'")
print(f"NQ count: {c.fetchone()[0]}")
conn.close()
