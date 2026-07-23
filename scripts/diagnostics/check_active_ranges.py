import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT account_name, symbol, MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades 
    GROUP BY account_name, symbol
    HAVING COUNT(*) > 1000
    ORDER BY MIN(entry_time)
''')
for row in cur:
    print(row)
conn.close()
