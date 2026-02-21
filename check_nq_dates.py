
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE symbol LIKE 'NQ%'")
print(f"NQ date range: {c.fetchone()}")
conn.close()
