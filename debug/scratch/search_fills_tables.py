import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%fill%' OR name LIKE '%execution%')")
tables = cursor.fetchall()
for table in tables:
    print(f"Table: {table[0]}")
    cursor.execute(f"PRAGMA table_info({table[0]})")
    cols = cursor.fetchall()
    for col in cols:
        print(f"  Column: {col[1]}")
conn.close()
