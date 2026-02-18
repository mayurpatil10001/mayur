import sqlite3
import os

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit()

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"Tables in database: {tables}")

if 'processed_trades' in tables:
    c.execute("SELECT entry_time, exit_time, symbol, profit_loss FROM processed_trades WHERE account_name = '3Q_SIM13' ORDER BY entry_time DESC LIMIT 10")
    print("Last 10 trades for SIM13:")
    for row in c.fetchall():
        print(row)
else:
    print("Table 'processed_trades' NOT FOUND!")

if 'fills' in tables:
    c.execute("SELECT timestamp, symbol, side, quantity, price FROM fills WHERE account_name = '3Q_SIM13' ORDER BY timestamp DESC LIMIT 10")
    print("\nLast 10 fills for SIM13:")
    for row in c.fetchall():
        print(row)

conn.close()
