import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Last 5 entries in data_import_log:")
cursor.execute("SELECT id, timestamp, status, total_processed, message FROM data_import_log ORDER BY id DESC LIMIT 5")
for r in cursor.fetchall():
    print(r)

conn.close()
