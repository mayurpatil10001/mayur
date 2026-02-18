import sqlite3
import datetime

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()

print("Trade counts per account:")
cur.execute("SELECT account_name, COUNT(*), MAX(exit_time) FROM processed_trades GROUP BY account_name")
for row in cur.fetchall():
    print(f" - {row[0]}: {row[1]} trades, Last exit: {row[2]}")

print("\nRecent 5 trades for IPS_TM_7:")
cur.execute("SELECT entry_time, exit_time, symbol, profit_loss FROM processed_trades WHERE account_name = 'IPS_TM_7' ORDER BY exit_time DESC LIMIT 5")
for row in cur.fetchall():
    print(f" - {row[0]} -> {row[1]} | {row[2]} | ${row[3]}")

conn.close()
