import sqlite3
import pandas as pd

DB = 'trading_platform.db'
conn = sqlite3.connect(DB)

print("=== V_SIM16 Trades in processed_trades Table ===")
try:
    cols = pd.read_sql('PRAGMA table_info(processed_trades)', conn)
    print("Columns:", cols['name'].tolist())
    
    # Check V_SIM16 count
    count = pd.read_sql('SELECT count(*) as count FROM processed_trades WHERE account_name = "V_SIM16"', conn)
    print(f"V_SIM16 count: {count['count'][0]}")
    
    # Sample
    df = pd.read_sql('SELECT entry_time, exit_time, symbol, quantity, profit_loss FROM processed_trades WHERE account_name = "V_SIM16" LIMIT 10', conn)
    print(df)
except Exception as e:
    print(f"Error: {e}")

conn.close()
