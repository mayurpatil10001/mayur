import sqlite3
DB = "trading_platform.db"
conn = sqlite3.connect(DB)
c = conn.cursor()
print("--- TABLE SCHEMA ---")
c.execute("SELECT sql FROM sqlite_master WHERE name='processed_trades'")
print(c.fetchone()[0])

print("\n--- INDEXES ---")
c.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='processed_trades'")
for row in c.fetchall():
    print(row)

print("\n--- QUERY PLAN PREVIEW (for slow query) ---")
# Example query that might be slow
# SELECT account_name, symbol, COUNT(*) FROM processed_trades GROUP BY account_name, symbol
try:
    c.execute("EXPLAIN QUERY PLAN SELECT account_name, symbol, COUNT(*) FROM processed_trades GROUP BY account_name, symbol")
    for row in c.fetchall():
        print(row)
except Exception as e:
    print(f"Query plan failed: {e}")
conn.close()
