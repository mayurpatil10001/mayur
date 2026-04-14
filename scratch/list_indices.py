import sqlite3
conn = sqlite3.connect("trading_platform.db")
indexes = conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='processed_trades'").fetchall()
for name, sql in indexes:
    print(f"Index: {name}\nSQL: {sql}\n")
conn.close()
