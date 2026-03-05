
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

# Get all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]

for table in tables:
    try:
        c.execute(f"PRAGMA table_info({table})")
        cols = [col[1] for col in c.fetchall()]
        for col in cols:
            query = f"SELECT {col} FROM {table} WHERE {col} LIKE '%T%-%' OR {col} LIKE '%T%+%' LIMIT 1"
            c.execute(query)
            res = c.fetchone()
            if res:
                print(f"Found offset in table '{table}', column '{col}': {res[0]}")
    except:
        continue

conn.close()
