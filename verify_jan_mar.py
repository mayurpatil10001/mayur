import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT strftime('%Y-%m', entry_time) as month, COUNT(*) as trades
    FROM processed_trades 
    WHERE account_name = "V_SIM16" AND entry_time LIKE '2025-%'
    GROUP BY month
    ORDER BY month
''')
stats = cur.fetchall()
print(f"Monthly trade counts for V_SIM16 in 2025:")
for s in stats:
    print(s)
conn.close()
