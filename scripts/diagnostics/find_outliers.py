import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT trade_id, entry_time, exit_time, profit_loss, symbol 
    FROM processed_trades 
    WHERE account_name = "V_SIM16" AND ABS(profit_loss) > 10000 
    ORDER BY ABS(profit_loss) DESC
''')
trades = cur.fetchall()
print(f"Outlier trades for V_SIM16 (|PnL| > $10,000):")
for t in trades:
    print(t)
conn.close()
