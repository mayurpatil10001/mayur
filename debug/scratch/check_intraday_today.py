import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("Checking for Intraday trades on 2026-02-24 (Entry & Exit today):")
cursor.execute("""
    SELECT count(*) FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
      AND entry_time >= '2026-02-24T00:00:00'
""")
count = cursor.fetchone()[0]
print(f"Total: {count}")

conn.close()
