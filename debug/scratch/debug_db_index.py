import sqlite3
conn = sqlite3.connect('trading_platform.db')
c = conn.cursor()
c.execute("PRAGMA index_info('idx_proc_trades_acc_sym')")
print("Index Info:", c.fetchall())
conn.close()
