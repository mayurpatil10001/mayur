import sqlite3
import pandas as pd
from pathlib import Path

db_path = Path("trading_platform.db")
conn = sqlite3.connect(db_path)

print("Sample V_SIM16 trades on 2025-12-18:")
df = pd.read_sql_query("""
    SELECT entry_time, exit_time, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC 
    LIMIT 20
""", conn)

# Set pandas options for better visibility
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)
pd.set_option('display.max_rows', 100)

print(df)

conn.close()
