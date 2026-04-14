import sqlite3
import time

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

accounts = ['TM_8', 'TM_5']
print(f"Checking for recent trades for {accounts}...")

for acc in accounts:
    cursor.execute("""
        SELECT symbol, MAX(entry_time) as last_trade, COUNT(*) as recent_count
        FROM processed_trades
        WHERE account_name = ? AND entry_time >= date('now', '-30 days')
        GROUP BY symbol
    """, (acc,))
    rows = cursor.fetchall()
    if not rows:
        print(f"Account {acc} has ZERO trades in the last 30 days across ALL symbols.")
    else:
        for r in rows:
            print(f"Account {acc} has {r['recent_count']} trades in {r['symbol']} (Last: {r['last_trade']})")

conn.close()
