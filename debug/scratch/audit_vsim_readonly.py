import sqlite3
import pandas as pd
from pathlib import Path

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 200)
pd.set_option('display.max_rows', 100)

db_path = Path("trading_platform.db")
conn = sqlite3.connect(db_path)

# Note: I cleared V_SIM16 earlier manually. Check if it's empty now or if re-import added data back
print("=== V_SIM16 trade count ===")
res = conn.execute("SELECT COUNT(*) FROM processed_trades WHERE UPPER(account_name) = 'V_SIM16'").fetchone()
print(f"Total: {res[0]}")

if res[0] > 0:
    print("\n=== First 5 trades (earliest) ===")
    df = pd.read_sql_query("""
        SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss
        FROM processed_trades
        WHERE UPPER(account_name) = 'V_SIM16'
        ORDER BY entry_time ASC LIMIT 5
    """, conn)
    for _, r in df.iterrows():
        print(f"  {r['entry_time']}  {r['side']:5s}  qty={r['quantity']}  entry={r['entry_price']}  exit={r['exit_price']}  pnl={r['profit_loss']}")

    print("\n=== Trades on 2025-12-18 ===")
    df2 = pd.read_sql_query("""
        SELECT entry_time, exit_time, side, quantity, entry_price, exit_price, profit_loss
        FROM processed_trades
        WHERE UPPER(account_name) = 'V_SIM16' AND entry_time LIKE '2025-12-18%'
        ORDER BY entry_time ASC LIMIT 10
    """, conn)
    for _, r in df2.iterrows():
        print(f"  {r['entry_time']}  {r['side']:5s}  qty={r['quantity']}  entry={r['entry_price']}  exit={r['exit_price']}  pnl={r['profit_loss']}")

    print(f"\n  Total trades on 2025-12-18: {len(df2)}")

    print("\n=== Date range and symbol ===")
    res2 = conn.execute("""
        SELECT symbol, MIN(entry_time) as first, MAX(entry_time) as last, COUNT(*) as cnt
        FROM processed_trades WHERE UPPER(account_name) = 'V_SIM16'
        GROUP BY symbol
    """).fetchall()
    for r in res2:
        print(f"  Symbol={r[0]}  First={r[1]}  Last={r[2]}  Count={r[3]}")
else:
    print("V_SIM16 has been cleared (no trades in DB). User needs to re-import.")

conn.close()
