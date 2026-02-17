import sqlite3
conn = sqlite3.connect('trading_platform.db')
cursor = conn.cursor()
count = cursor.execute("SELECT COUNT(*) FROM processed_trades").fetchone()[0]
print(f"Total trades: {count}")
if count > 0:
    prefix_counts = cursor.execute("SELECT SUBSTR(trade_id, 1, 4), COUNT(*) FROM processed_trades GROUP BY SUBSTR(trade_id, 1, 4)").fetchall()
    print("Prefix counts:", prefix_counts)
    sample = cursor.execute("SELECT trade_id, account_name, symbol FROM processed_trades LIMIT 3").fetchall()
    print("Sample trades:", sample)
conn.close()
