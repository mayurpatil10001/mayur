import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check what SQLite thinks is "-30 days"
cursor.execute("SELECT date('now', '-30 days'), datetime('now', '-30 days')")
d, dt = cursor.fetchone()
print(f"SQLite 30d cutoff: date={d}, datetime={dt}")

# Check TM_8's latest trade on NQ
cursor.execute("SELECT MAX(entry_time) FROM processed_trades WHERE account_name='TM_8' AND symbol='NQ'")
last_trade = cursor.fetchone()[0]
print(f"TM_8 latest trade on NQ: {last_trade}")

# Check TM_8's latest trade on ANY symbol
cursor.execute("SELECT symbol, MAX(entry_time) FROM processed_trades WHERE account_name='TM_8' GROUP BY symbol")
rows = cursor.fetchall()
print(f"TM_8 latest trade on ANY symbol: {rows}")

conn.close()
