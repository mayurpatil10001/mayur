import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    cursor.execute(f"PRAGMA table_info({table[0]})")
    cols = cursor.fetchall()
    for col in cols:
        if col[1].lower() == 'notes' or col[1].lower() == 'note':
            print(f"Table '{table[0]}' has column '{col[1]}'")
conn.close()
