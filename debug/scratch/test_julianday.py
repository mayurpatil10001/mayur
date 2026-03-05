import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

# Create a test table
conn.execute("CREATE TEMP TABLE test_dt (t1 TEXT, t2 TEXT)")
conn.execute("INSERT INTO test_dt VALUES ('2026-02-19T11:41:42.568828', '2026-02-24T00:18:59.775794')")

res = conn.execute("SELECT julianday(t2) - julianday(t1) FROM test_dt").fetchone()[0]
print(f"Diff: {res}")

conn.close()
