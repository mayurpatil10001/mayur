import sqlite3
conn = sqlite3.connect('trading_platform.db')
rows = conn.execute("SELECT account_name, count(*) FROM processed_trades GROUP BY account_name ORDER BY count(*) DESC LIMIT 10").fetchall()
for r in rows:
    print(f"{r[0]}: {r[1]}")
