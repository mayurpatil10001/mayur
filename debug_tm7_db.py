import sqlite3
conn = sqlite3.connect(r'c:\SC_results_WF\trading_platform.db')
cur = conn.cursor()

# Check TM_7 NQ sample rows
cur.execute("""
    SELECT account_name, symbol, entry_time, exit_time, entry_price, exit_price, profit_loss
    FROM processed_trades
    WHERE account_name='TM_7' AND symbol LIKE 'NQ%'
    ORDER BY entry_time
    LIMIT 10
""")
rows = cur.fetchall()
print("=== TM_7 NQ DB samples ===")
for r in rows:
    print(r)

# Check date range
cur.execute("""
    SELECT MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades
    WHERE account_name='TM_7' AND symbol LIKE 'NQ%'
""")
print("\n=== TM_7 NQ date range ===")
print(cur.fetchone())

# Check all TM*7 accounts and their NQ date ranges
cur.execute("""
    SELECT account_name, symbol, MIN(entry_time), MAX(entry_time), COUNT(*)
    FROM processed_trades
    WHERE (account_name LIKE '%TM%7%') AND symbol LIKE 'NQ%'
    GROUP BY account_name, symbol
""")
print("\n=== All TM*7 NQ accounts date ranges ===")
for r in cur.fetchall():
    print(r)

conn.close()
