import sqlite3
DB = "trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print(f"{'Table':<25} | {'Rows':<10}")
print("-" * 40)
for t in tables:
    c.execute(f"SELECT COUNT(*) FROM {t}")
    count = c.fetchone()[0]
    print(f"{t:<25} | {count:<10}")
conn.close()
