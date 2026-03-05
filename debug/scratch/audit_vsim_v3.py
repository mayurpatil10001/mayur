import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_platform.db')

print("=== V_SIM16 Trades on Dec 18 (UTC) ===")
# Show first 10 trades for V_SIM16 on Dec 18
df = pd.read_sql('SELECT entry_time, exit_time, symbol, volume, net_profit FROM trades WHERE account = "V_SIM16" AND entry_time LIKE "2025-12-18%" LIMIT 10', conn)
print(df)

print("\n=== All Accounts List (Top 20 by trade count) ===")
accs = pd.read_sql('SELECT account, COUNT(*) as count FROM trades GROUP BY account ORDER BY count DESC LIMIT 20', conn)
print(accs)

conn.close()
