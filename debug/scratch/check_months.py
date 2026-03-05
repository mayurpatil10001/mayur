import sqlite3
DB = "trading_platform.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== TRADE DISTRIBUTION (By Month) ===")
# NQ
print("\n[ NQ ]")
c.execute("""
    SELECT strftime('%Y-%m', entry_time) as month, COUNT(*) as cnt
    FROM processed_trades
    WHERE symbol = 'NQ'
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 12
""")
for r in c.fetchall():
    print(f"  {r['month']}: {r['cnt']:,} trades")

# FDAX
print("\n[ FDAX ]")
c.execute("""
    SELECT strftime('%Y-%m', entry_time) as month, COUNT(*) as cnt
    FROM processed_trades
    WHERE symbol = 'FDAX'
    GROUP BY 1
    ORDER BY 1 DESC
    LIMIT 12
""")
for r in c.fetchall():
    print(f"  {r['month']}: {r['cnt']:,} trades")

# Check FDAX Path again but specifically for filename patterns
import os, glob
fdax_path = r"D:\SierraChart_Delayed_Simulated\TradeActivityLogs"
files = glob.glob(os.path.join(fdax_path, "*"))
print(f"\nFDAX Files in Path: {len(files)}")
if files:
    print("Sample Fnames:")
    for f in sorted(files)[:5]:
        print(f"  {os.path.basename(f)} (mtime: {os.path.getmtime(f)})")

conn.close()
