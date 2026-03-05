
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()

# Get all tables
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in c.fetchall()]

target = "2024-02-20T09:30:00-05:00"

for table in tables:
    try:
        c.execute(f"PRAGMA table_info({table})")
        cols = [col[1] for col in c.fetchall()]
        for col in cols:
            query = f"SELECT COUNT(*) FROM {table} WHERE {col} = ?"
            c.execute(query, (target,))
            count = c.fetchone()[0]
            if count > 0:
                print(f"Found {count} matches in table '{table}', column '{col}'")
    except:
        continue

conn.close()
