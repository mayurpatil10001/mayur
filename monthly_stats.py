import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT strftime('%Y-%m', entry_time) as month, SUM(profit_loss) as total_pnl, COUNT(*) as trades
    FROM processed_trades 
    WHERE account_name = "V_SIM16"
    GROUP BY month
    ORDER BY month
''')
stats = cur.fetchall()
print(f"Monthly stats for V_SIM16:")
for s in stats:
    print(s)
conn.close()
