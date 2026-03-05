import sqlite3
import pandas as pd

DB = 'trading_platform.db'
conn = sqlite3.connect(DB)

print("=== V_SIM16 Trade Sample (UTC) ===")
# Show a few trades from Dec 18 (matching your SC screenshot)
df = pd.read_sql('SELECT entry_time, exit_time, symbol, quantity, profit_loss FROM trades WHERE account = "V_SIM16" AND entry_time LIKE "2025-12-18%" LIMIT 10', conn)
print(df)

print("\n=== Account Stats (Dropdown Check) ===")
try:
    stats = pd.read_sql('SELECT account, count(*) as trade_count FROM trades GROUP BY account', conn)
    print(stats)
except:
    print("Table 'trades' has no column 'account'?")

conn.close()
