import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('''
    SELECT date(entry_time) as trade_day, SUM(profit_loss) as total_pnl, COUNT(*) as trades
    FROM processed_trades 
    WHERE account_name = "V_SIM16" AND entry_time LIKE '2025-04%'
    GROUP BY trade_day
    ORDER BY total_pnl DESC
''')
days = cur.fetchall()
print(f"Daily PnL for V_SIM16 in April 2025:")
for d in days:
    print(d)
conn.close()
