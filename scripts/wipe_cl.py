import sqlite3

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()
accounts = ['3Q_SIM13', '3Q_SIM14', '3Q_SIM15']
for acc in accounts:
    c.execute("DELETE FROM processed_trades WHERE account_name = ?", (acc,))
    c.execute("DELETE FROM temporal_performance WHERE account_name = ?", (acc,))
conn.commit()
conn.close()
print("Wiped all trades and performance for SIM13, 14, 15")
