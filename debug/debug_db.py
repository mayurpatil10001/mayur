import sqlite3
import datetime

db_path = r'c:\SierraChart\SC results WF\trading_platform\database.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("--- LAST 5 TRADES FOR 3Q_SIM13 ---")
c.execute("SELECT entry_time, exit_time, symbol, profit_loss FROM processed_trades WHERE account_name = '3Q_SIM13' ORDER BY entry_time DESC LIMIT 5")
for row in c.fetchall():
    print(row)

print("\n--- UNPAIRED FILLS FOR 3Q_SIM13 ---")
c.execute("SELECT timestamp, symbol, quantity, price, side FROM fills WHERE account_name = '3Q_SIM13' ORDER BY timestamp DESC LIMIT 5")
for row in c.fetchall():
    print(row)

conn.close()
