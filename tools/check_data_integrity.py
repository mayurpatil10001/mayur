
import sqlite3
import datetime

conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

print("--- DATE FORMAT CHECK ---")
c.execute("SELECT entry_time, exit_time FROM processed_trades LIMIT 10")
for r in c.fetchall():
    print(f"Entry: {r[0]} | Exit: {r[1]}")

print("\n--- CHECKING FOR NON-ISO DATES ---")
c.execute("SELECT trade_id, entry_time FROM processed_trades")
bad_entries = 0
for tid, et in c.fetchall():
    try:
        if et:
            datetime.datetime.fromisoformat(et.replace('Z', '+00:00'))
    except Exception as e:
        if bad_entries < 5:
            print(f"Bad Trade {tid}: {et} -> {e}")
        bad_entries += 1

print(f"Total Bad Dates: {bad_entries}")

print("\n--- ACCOUNT LIST CHECK ---")
c.execute("SELECT DISTINCT account_name, symbol FROM processed_trades")
for r in c.fetchall():
    print(f"Account: {r[0]} | Symbol: {r[1]}")

conn.close()
