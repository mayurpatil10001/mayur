import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("Last 5 entries in data_import_log:")
cursor.execute("SELECT id, import_timestamp, import_status, records_imported, error_message FROM data_import_log ORDER BY id DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)

conn.close()
