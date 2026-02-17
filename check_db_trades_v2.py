import sqlite3
conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()

print("Status for IPS_TM_7:")
cur.execute("SELECT COUNT(*), MIN(exit_time), MAX(exit_time) FROM processed_trades WHERE account_name = 'IPS_TM_7'")
count, first, last = cur.fetchone()
print(f"Total trades: {count}")
print(f"First Exit: {first}")
print(f"Last Exit:  {last}")

print("\nLast 10 exits for IPS_TM_7:")
cur.execute("SELECT exit_time, symbol, profit_loss FROM processed_trades WHERE account_name = 'IPS_TM_7' ORDER BY exit_time DESC LIMIT 10")
for row in cur.fetchall():
    print(f" - {row[0]} | {row[1]} | ${row[2]}")

conn.close()
