import sqlite3

conn = sqlite3.connect('trading_platform.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

query = """
SELECT 
    account_name,
    symbol,
    COUNT(*) as total_trades,
    MIN(entry_time) as first_trade_date,
    MAX(exit_time) as last_trade_date,
    SUM(profit_loss) as total_pnl,
    1 as is_active
FROM processed_trades 
GROUP BY account_name, symbol 
ORDER BY account_name, symbol
"""

cursor.execute(query)
rows = cursor.fetchall()
print(f"Query found {len(rows)} results.")
for row in rows[:5]:
    print(dict(row))
conn.close()
