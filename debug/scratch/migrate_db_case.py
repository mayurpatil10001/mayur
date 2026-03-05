import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Migrating account names to UPPERCASE...")

# Update processed_trades
cursor.execute("UPDATE processed_trades SET account_name = UPPER(account_name)")
print(f"Updated {cursor.rowcount} rows in processed_trades")

# Update pending_fills
cursor.execute("UPDATE pending_fills SET account_name = UPPER(account_name)")
print(f"Updated {cursor.rowcount} rows in pending_fills")

conn.commit()
conn.close()
print("Migration complete.")
