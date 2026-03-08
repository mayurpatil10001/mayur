import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT symbol, MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades 
    WHERE account_name = "V_SIM16"
    GROUP BY symbol
''')
stats = cur.fetchall()
print(f"Stats for V_SIM16 by symbol:")
for s in stats:
    print(s)
conn.close()
