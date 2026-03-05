import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_platform.db')
print("=== V_SIM16 Dec 18 Trades in DB ===")
df = pd.read_sql('SELECT entry_time, exit_time, trade_type, volume, net_profit FROM trades WHERE account = "V_SIM16" AND entry_time LIKE "2025-12-18%" LIMIT 20', conn)
print(df)
conn.close()
