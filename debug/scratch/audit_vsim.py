import sqlite3
import pandas as pd

conn = sqlite3.connect('trades.db')

print("=== V_SIM16 Trade Sample ===")
df = pd.read_sql('SELECT entry_time, exit_time, symbol, quantity, profit_loss FROM trades WHERE account = "V_SIM16" LIMIT 10', conn)
print(df)

print("\n=== All Accounts in DB ===")
accs = pd.read_sql('SELECT DISTINCT account FROM trades', conn)
print(accs['account'].tolist())

# Check if V_SIM16 is in the analytics cache table (if it exists)
try:
    cache = pd.read_sql('SELECT account_name FROM account_stats', conn)
    print("\n=== Accounts in Stats Cache ===")
    print(cache['account_name'].tolist())
except:
    print("\nNo account_stats table found.")

conn.close()
