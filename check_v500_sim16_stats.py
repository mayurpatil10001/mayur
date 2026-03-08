import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT account_name, symbol, MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades 
    WHERE account_name = "V500_SIM16"
    GROUP BY symbol
''')
for row in cur:
    print(row)
conn.close()
