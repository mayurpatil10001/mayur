
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("PRAGMA table_info(processed_trades)")
cols = c.fetchall()
for col in cols:
    print(col)
conn.close()
