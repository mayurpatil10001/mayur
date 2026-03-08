import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT trade_id, entry_time, exit_time, profit_loss, symbol 
    FROM processed_trades 
    WHERE account_name = "V_SIM16" AND entry_time LIKE '2025-04%'
    ORDER BY ABS(profit_loss) DESC
    LIMIT 20
''')
trades = cur.fetchall()
print(f"Top 20 trades for V_SIM16 in April 2025:")
for t in trades:
    print(t)
conn.close()
