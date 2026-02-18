import sqlite3

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("""
    SELECT COUNT(*), SUM(profit_loss) 
    FROM processed_trades 
    WHERE account_name = 'TS_4' AND symbol = 'CL'
""")
count, pnl = c.fetchone()

print(f"TS_4 CL Statistics:")
print(f"Total Trades: {count}")
print(f"Total PnL: ${pnl:,.2f}" if pnl is not None else "Total PnL: $0.00")

# Break down by month/year if possible to see the distribution
c.execute("""
    SELECT strftime('%Y-%m', entry_time) as month, COUNT(*), SUM(profit_loss)
    FROM processed_trades
    WHERE account_name = 'TS_4' AND symbol = 'CL'
    GROUP BY month
    ORDER BY month
""")
rows = c.fetchall()
print("\nMonthly Breakdown:")
for row in rows:
    print(f"{row[0]}: {row[1]} trades, ${row[2]:,.2f}")

conn.close()
