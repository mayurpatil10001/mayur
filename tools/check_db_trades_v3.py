import sqlite3
conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()

print("Trade counts for IPS_TM_7 by symbol:")
cur.execute("SELECT symbol, COUNT(*), MIN(exit_time), MAX(exit_time) FROM processed_trades WHERE account_name = 'IPS_TM_7' GROUP BY symbol")
for row in cur.fetchall():
    print(f" - {row[0]}: {row[1]} trades, Last exit: {row[2]}")

conn.close()
