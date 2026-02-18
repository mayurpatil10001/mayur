
import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
print("--- TABLES ---")
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
for t in c.fetchall():
    print(t[0])
    c.execute(f"PRAGMA table_info({t[0]})")
    for col in c.fetchall():
        print(f"  {col[1]} ({col[2]})")

print("\n--- INDEXES ---")
c.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
for idx in c.fetchall():
    print(f"{idx[0]}: {idx[1]}")
conn.close()
