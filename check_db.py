import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.execute("PRAGMA table_info(processed_trades)")
for row in cursor:
    print(row)
conn.close()
