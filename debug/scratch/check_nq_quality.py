import sqlite3
DB = "trading_platform.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=== NQ QUALITY CHECK ===")
c.execute("""
    SELECT account_name, symbol, entry_time, exit_time, profit_loss, quantity, entry_price, exit_price
    FROM processed_trades
    WHERE symbol = 'NQ' AND (abs(profit_loss) > 50000 OR abs(profit_loss) < 0.1)
    LIMIT 20
""")
rows = c.fetchall()
if not rows:
    print("No extreme outliers or zero-pnl trades found in sample.")
else:
    for r in rows:
        print(f"{r['account_name']} | PnL: ${r['profit_loss']:,.2f} | {r['entry_time']}")

print("\n=== TOP 20 NQ TRADES BY PNL ===")
c.execute("""
    SELECT account_name, profit_loss, entry_time
    FROM processed_trades
    WHERE symbol = 'NQ'
    ORDER BY abs(profit_loss) DESC
    LIMIT 10
""")
for r in c.fetchall():
    print(f"{r['account_name']} | ${r['profit_loss']:,.2f} | {r['entry_time']}")

conn.close()
