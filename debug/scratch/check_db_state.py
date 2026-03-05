import sqlite3
import pandas as pd

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

# 1. Check verified trades in DB
print("--- PROCESSED TRADES (Completed Pairs) ---")
query_trades = """
SELECT 
    trade_id, 
    entry_time, 
    exit_time, 
    quantity, 
    profit_loss,
    side
FROM processed_trades 
WHERE account_name = 'V_SIM16' 
  AND entry_time LIKE '2025-12-18%'
ORDER BY entry_time ASC;
"""
df_trades = pd.read_sql_query(query_trades, conn)
print(df_trades.to_string(index=False))

# 2. Check if there are any hanging fills (unpaired) that the system is visibility reporting
print("\n--- UNPAIRED FILLS (Hanging entries/exits) ---")
# Assuming there is a table for unpaired fills or we can check the import_debug.log
# For now, let's just see if we can find any raw fills in the DB that aren't matched if such a table exists.
# I will check the table list first.
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print(f"\nTables in DB: {[t[0] for t in tables]}")

conn.close()
