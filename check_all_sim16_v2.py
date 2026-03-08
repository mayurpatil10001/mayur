import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT account_name, symbol, MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades 
    WHERE account_name LIKE "%SIM16"
    GROUP BY account_name, symbol
''')
stats = cur.fetchall()
print(f"Stats for all SIM16 accounts:")
for s in stats:
    print(s)
conn.close()
