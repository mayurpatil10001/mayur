import sqlite3
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(PROJECT_ROOT, "trading_platform_clean_v2.db")

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

rows = con.execute("""
    SELECT 
        base_symbol,
        COUNT(DISTINCT account) as accounts,
        COUNT(*) as total_trades,
        SUM(CASE WHEN pnl_dollars > 0 THEN 1 ELSE 0 END) as wins,
        SUM(CASE WHEN pnl_dollars <= 0 THEN 1 ELSE 0 END) as losses,
        SUM(pnl_dollars) as net_pnl,
        MIN(pnl_dollars) as min_pnl,
        MAX(pnl_dollars) as max_pnl
    FROM clean_trades
    GROUP BY base_symbol
    ORDER BY total_trades DESC
""").fetchall()

print("Symbol | Accounts | Clean Trades | Wins | Losses | Net PnL | Worst Trade | Best Trade")
print("-" * 90)
for r in rows:
    print(f"{r['base_symbol']} | {r['accounts']} | {r['total_trades']:,} | {r['wins']:,} | {r['losses']:,} | ${r['net_pnl']:,.2f} | ${r['min_pnl']:,.2f} | +${r['max_pnl']:,.2f}")

con.close()


