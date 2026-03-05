import sqlite3
DB = r"C:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables in DB:")
for r in c.fetchall():
    print(f"  {r[0]}")
conn.close()
