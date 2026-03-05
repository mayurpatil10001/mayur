import sqlite3
DB = "trading_platform.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== NQ IMPORT SUMMARY ===")
c.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT account_name) as accounts,
        SUM(profit_loss) as total_pnl,
        MIN(entry_time) as start,
        MAX(exit_time) as end
    FROM processed_trades
    WHERE symbol = 'NQ'
""")
res = c.fetchone()
print(f"Total NQ Trades: {res['total']:,}")
print(f"Accounts: {res['accounts']}")
print(f"Total PnL: ${res['total_pnl']:,.2f}")
print(f"Range: {res['start']} to {res['end']}")

print("\n=== FDAX IMPORT SUMMARY ===")
c.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT account_name) as accounts,
        SUM(profit_loss) as total_pnl,
        MIN(entry_time) as start,
        MAX(exit_time) as end
    FROM processed_trades
    WHERE symbol = 'FDAX'
""")
res = c.fetchone()
print(f"Total FDAX Trades: {res['total']:,}")
print(f"Accounts: {res['accounts']}")
print(f"Total PnL: ${res['total_pnl']:,.2f}")
print(f"Range: {res['start']} to {res['end']}")

conn.close()
