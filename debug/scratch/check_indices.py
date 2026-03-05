
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='processed_trades'")
indices = c.fetchall()
for idx in indices:
    print(idx)
conn.close()
