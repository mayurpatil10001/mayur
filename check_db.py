
import sqlite3
import os

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"

if not os.path.exists(db_path):
    print(f"Error: Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    cursor.execute("SELECT count(*) FROM processed_trades")
    total_trades = cursor.fetchone()[0]
    print(f"Total trades: {total_trades}")

    cursor.execute("SELECT account_name, count(*) FROM processed_trades GROUP BY account_name")
    accounts = cursor.fetchall()
    print("Trades per account:")
    for acc, count in accounts:
        print(f" - {acc}: {count}")

    cursor.execute("SELECT entry_time FROM processed_trades ORDER BY entry_time ASC LIMIT 1")
    first = cursor.fetchone()
    cursor.execute("SELECT entry_time FROM processed_trades ORDER BY entry_time DESC LIMIT 1")
    last = cursor.fetchone()
    print(f"Date range: {first[0] if first else 'N/A'} to {last[0] if last else 'N/A'}")

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
