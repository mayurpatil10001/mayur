import sqlite3
import os

db_path = r'c:\SierraChart\SC results WF\trading_platform\database.db'
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    # Try another location?
    exit()

conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"Tables in database: {tables}")

if 'processed_trades' in tables:
    c.execute("SELECT entry_time, exit_time FROM processed_trades WHERE account_name = '3Q_SIM13' ORDER BY entry_time DESC LIMIT 5")
    print("Last 5 trades for SIM13:")
    for row in c.fetchall():
        print(row)
else:
    print("Table 'processed_trades' NOT FOUND!")

if 'fills' in tables:
    c.execute("SELECT timestamp FROM fills WHERE account_name = '3Q_SIM13' ORDER BY timestamp DESC LIMIT 5")
    print("Last 5 fills for SIM13:")
    for row in c.fetchall():
        print(row)

conn.close()
