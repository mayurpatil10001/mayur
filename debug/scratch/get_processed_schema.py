import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Schema for processed_trades:")
cursor.execute("PRAGMA table_info(processed_trades)")
for c in cursor.fetchall():
    print(c)

conn.close()
