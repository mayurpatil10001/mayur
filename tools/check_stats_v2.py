import sqlite3

db_path = r"c:\SierraChart\SC results WF\trading_platform.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

print("All Accounts with CL Trades:")
c.execute("""
    SELECT account_name, COUNT(*), SUM(profit_loss)
    FROM processed_trades
    WHERE symbol LIKE '%CL%'
    GROUP BY account_name
""")
for row in c.fetchall():
    print(f"{row[0]}: {row[1]} trades, ${row[2]:,.2f}")

print("\nDetail for TS_4 related accounts (CL):")
c.execute("""
    SELECT strftime('%Y-%m', entry_time) as month, account_name, COUNT(*), SUM(profit_loss)
    FROM processed_trades
    WHERE account_name LIKE '%TS_4%' AND symbol LIKE '%CL%'
    GROUP BY month, account_name
    ORDER BY month, account_name
""")
for row in c.fetchall():
    print(f"{row[0]} | {row[1]}: {row[2]} trades, ${row[3]:,.2f}")

conn.close()
