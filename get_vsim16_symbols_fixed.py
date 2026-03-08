import sqlite3

conn = sqlite3.connect('trading_platform.db')
cur = conn.cursor()
cur.execute('SELECT DISTINCT symbol FROM processed_trades WHERE account_name = "V_SIM16"')
symbols = cur.fetchall()
print(f"Symbols traded by V_SIM16 in DB: {symbols}")
conn.close()
