import sqlite3
import pandas as pd
from pathlib import Path

db_path = Path("trading_platform.db")
conn = sqlite3.connect(db_path)

print("Checking processed_trades for V_SIM16 on 2025-12-18...")
df = pd.read_sql_query("""
    SELECT trade_id, account_name, symbol, entry_time, exit_time, quantity, side, profit_loss, entry_price, exit_price
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' 
    AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC
    LIMIT 10
""", conn)

print(df)

print("\nChecking if there are any other accounts with 'V_SIM16' in the name...")
df_accs = pd.read_sql_query("SELECT DISTINCT account_name FROM processed_trades WHERE account_name LIKE '%V_SIM16%'", conn)
print(df_accs)

conn.close()
