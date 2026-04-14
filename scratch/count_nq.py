import sqlite3
conn = sqlite3.connect("trading_platform.db")
count = conn.execute("SELECT count(*) FROM processed_trades WHERE symbol='NQ'").fetchone()[0]
print(f"NQ trades: {count}")
conn.close()
