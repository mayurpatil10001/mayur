import sqlite3
import pandas as pd
conn = sqlite3.connect(r'C:\SierraChart\SC results WF\trading_platform.db')
query = "SELECT * FROM processed_trades WHERE account_name LIKE '%16%' AND entry_time LIKE '%2025-12-18%'"
df = pd.read_sql_query(query, conn)
target = df[df['entry_time'].str.contains('04:05', na=False)]
print(target)
