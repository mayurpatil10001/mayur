import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT account_name, symbol, strftime('%Y-%m', entry_time) as month, COUNT(*) as trades
    FROM processed_trades 
    WHERE entry_time >= '2025-01-01' AND entry_time < '2025-04-01'
    GROUP BY account_name, symbol, month
    ORDER BY trades DESC
''')
stats = cur.fetchall()
print(f"Top accounts with trades in Jan-Mar 2025:")
for s in stats:
    print(s)
conn.close()
