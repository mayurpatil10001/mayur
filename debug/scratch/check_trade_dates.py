import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("SELECT date(entry_time), COUNT(*) FROM processed_trades WHERE account_name='V_SIM16' GROUP BY date(entry_time) ORDER BY date(entry_time) DESC LIMIT 10")
for row in c.fetchall():
    print(f"Date: {row[0]} | Trades: {row[1]}")
conn.close()
