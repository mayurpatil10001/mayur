import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(trades)")
cols = cursor.fetchall()
print("FULL COLUMNS FOR 'trades':")
for c in cols:
    print(c)

conn.close()
