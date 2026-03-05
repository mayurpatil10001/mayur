import sqlite3
import pandas as pd

db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
conn = sqlite3.connect(db_path)

query = """
SELECT 
    trade_id, 
    symbol, 
    side, 
    entry_time, 
    exit_time, 
    quantity, 
    profit_loss 
FROM processed_trades 
WHERE account_name = 'V_SIM16' 
  AND entry_time >= '2025-12-18T00:00:00'
  AND entry_time <= '2025-12-18T23:59:59'
ORDER BY entry_time ASC;
"""

df = pd.read_sql_query(query, conn)
conn.close()

if df.empty:
    print("No verified trades found for V_SIM16 on 2025-12-18.")
else:
    print(df.to_string(index=False))
