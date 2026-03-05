import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Schema for 'trades' table:")
cursor.execute("PRAGMA table_info(trades)")
columns = cursor.fetchall()
for col in columns:
    print(col)

print("\nLast 5 records in 'trades':")
cursor.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()
for r in rows:
    print(r)

conn.close()
