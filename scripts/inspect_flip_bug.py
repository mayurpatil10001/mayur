import sqlite3, os

con = sqlite3.connect('trading_platform.db')
con.row_factory = sqlite3.Row

print("=== processed_trades schema ===")
cols = con.execute("PRAGMA table_info(processed_trades)").fetchall()
for c in cols:
    print(f"  {c[1]:25s} {c[2]}")

print()
print("=== row count and date range ===")
r = con.execute("SELECT COUNT(*), MIN(entry_time), MAX(entry_time) FROM processed_trades").fetchone()
print(f"  rows={r[0]:,}  min={r[1]}  max={r[2]}")

print()
print("=== symbol breakdown ===")
rows = con.execute("""
    SELECT symbol, COUNT(*) as n, MIN(entry_time) as first, MAX(entry_time) as last
    FROM processed_trades GROUP BY symbol ORDER BY n DESC
""").fetchall()
for r in rows:
    print(f"  {r['symbol']:8s}  n={r['n']:>9,}  {str(r['first'])[:10]}..{str(r['last'])[:10]}")

print()
print("=== null/missing check ===")
for col in ["account_name","symbol","profit_loss","entry_time","exit_time"]:
    n = con.execute(f"SELECT COUNT(*) FROM processed_trades WHERE {col} IS NULL").fetchone()[0]
    print(f"  {col}: {n} NULLs")

print()
print("=== sample row ===")
r = con.execute("SELECT * FROM processed_trades LIMIT 1").fetchone()
for k in r.keys():
    print(f"  {k}: {r[k]}")

print()
print("=== yearly trade distribution ===")
rows = con.execute("""
    SELECT substr(entry_time,1,4) as yr, COUNT(*) as n
    FROM processed_trades GROUP BY yr ORDER BY yr
""").fetchall()
for r in rows:
    print(f"  {r['yr']}: {r['n']:>9,}")

print()
print("=== entry_time sample (5 rows) to understand format ===")
rows = con.execute("SELECT entry_time, exit_time, symbol FROM processed_trades LIMIT 5").fetchall()
for r in rows:
    print(f"  entry={r['entry_time']}  exit={r['exit_time']}  sym={r['symbol']}")

con.close()
