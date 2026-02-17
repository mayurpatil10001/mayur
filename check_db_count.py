import sqlite3
conn = sqlite3.connect('trading_platform.db')
count = conn.execute("SELECT COUNT(*) FROM processed_trades").fetchone()[0]
print(f"Total trades in DB: {count}")
if count > 0:
    rows = conn.execute("SELECT * FROM processed_trades LIMIT 5").fetchall()
    for r in rows:
        print(r)
conn.close()
