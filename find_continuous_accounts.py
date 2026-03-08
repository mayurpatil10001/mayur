import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT account_name, symbol, MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades 
    GROUP BY account_name, symbol
    HAVING MIN(entry_time) < '2024-06-01' AND MAX(entry_time) > '2025-12-31'
    ORDER BY COUNT(*) DESC
''')
stats = cur.fetchall()
print(f"Accounts spanning 2024-2026:")
for s in stats:
    print(s)
conn.close()
