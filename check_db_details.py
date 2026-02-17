import sqlite3

conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()

# Check if accounts table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
if cursor.fetchone():
    print("Accounts table exists. Content:")
    cursor.execute("SELECT * FROM accounts WHERE name LIKE '%3Q_sim15%'")
    print(cursor.fetchall())
else:
    print("Accounts table does not exist.")

# Check unique account names in processed_trades
print("\nUnique accounts in processed_trades:")
cursor.execute("SELECT DISTINCT account_name, symbol FROM processed_trades")
for row in cursor.fetchall():
    print(row)

conn.close()
