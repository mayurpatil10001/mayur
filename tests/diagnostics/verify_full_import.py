import sqlite3
import pandas as pd

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

accounts = ['3Q_SIM13', '3Q_SIM14', '3Q_SIM15']

print("--- IMPORT VERIFICATION ---")

for acc in accounts:
    print(f"\nAccount: {acc}")
    
    # 1. Date Range
    c.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE account_name = ?", (acc,))
    dates = c.fetchone()
    print(f"  Date Range: {dates[0]}  TO  {dates[1]}")
    
    # 2. Trade Count
    c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = ?", (acc,))
    count = c.fetchone()[0]
    print(f"  Total Trades: {count}")
    
    # 3. Check for 2024 data
    c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = ? AND entry_time LIKE '2024%'", (acc,))
    count_2024 = c.fetchone()[0]
    print(f"  2024 Trades: {count_2024}")
    
    # 4. Check for latest data (Feb 2026)
    c.execute("SELECT COUNT(*) FROM processed_trades WHERE account_name = ? AND entry_time LIKE '2026-02%'", (acc,))
    count_feb26 = c.fetchone()[0]
    print(f"  Feb 2026 Trades: {count_feb26}")

print("\n--- SIM15 SPECIFIC CHECKS ---")
# Check Feb 17 specifically
c.execute("SELECT * FROM processed_trades WHERE account_name = '3Q_SIM15' AND entry_time LIKE '2026-02-17%'")
rows = c.fetchall()
print(f"SIM15 Feb 17 Trades: {len(rows)}")
if rows:
    print(f"  Sample: {rows[0]}")

conn.close()
