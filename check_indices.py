import sqlite3
conn = sqlite3.connect(r'c:\SierraChart\SC results WF\trading_platform.db')
for row in conn.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='processed_trades'").fetchall():
    print(row)
