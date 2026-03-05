
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]

for table in tables:
    try:
        c.execute(f"PRAGMA table_info({table})")
        cols = [col[1] for col in c.fetchall()]
        for col in cols:
            # specifically check for strings like '2024-02-20T09:30:00-05:00'
            c.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE '%T%:%-%'")
            count = c.fetchone()[0]
            if count > 0:
                c.execute(f"SELECT {col} FROM {table} WHERE {col} LIKE '%T%:%-%' LIMIT 1")
                val = c.fetchone()[0]
                print(f"Found {count} bad ISO strings in {table}.{col}. Sample: {val}")
    except Exception as e:
        # print(f"Error checking {table}: {e}")
        continue

conn.close()
