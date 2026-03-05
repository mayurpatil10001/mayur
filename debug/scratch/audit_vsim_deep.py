import sqlite3
import pandas as pd
from pathlib import Path

db_path = Path("trading_platform.db")
conn = sqlite3.connect(db_path)

print("--- V_SIM16 Audit ---")

# 1. Total counts in processed_trades
res = pd.read_sql_query("SELECT COUNT(*) as cnt FROM processed_trades WHERE account_name = 'V_SIM16'", conn)
print(f"Total trades for V_SIM16 in processed_trades: {res['cnt'][0]}")

# 2. Check for duplicates (same ID)
res = pd.read_sql_query("SELECT trade_id, COUNT(*) as cnt FROM processed_trades WHERE account_name = 'V_SIM16' GROUP BY trade_id HAVING cnt > 1 LIMIT 5", conn)
if not res.empty:
    print("Found duplicated trade_ids in processed_trades:")
    print(res)
else:
    print("No duplicated trade_ids found in processed_trades.")

# 3. Check pending_fills
res = pd.read_sql_query("SELECT COUNT(*) as cnt FROM pending_fills WHERE account_name = 'V_SIM16'", conn)
print(f"Total pending_fills for V_SIM16: {res['cnt'][0]}")

# 4. Sample trades on Dec 18
print("\nSample V_SIM16 trades on 2025-12-18:")
df = pd.read_sql_query("""
    SELECT entry_time, exit_time, symbol, side, quantity, profit_loss, entry_price, exit_price
    FROM processed_trades 
    WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-12-18%'
    ORDER BY entry_time ASC 
    LIMIT 20
""", conn)
print(df)

conn.close()
