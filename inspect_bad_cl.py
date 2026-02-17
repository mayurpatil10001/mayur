import sqlite3
import pandas as pd
from datetime import datetime

def inspect_bad_prices():
    conn = sqlite3.connect('trading_platform.db')
    
    # 1. Inspect CL trades with suspicious prices (> 150)
    print("--- Suspicious CL Prices (> 300) ---")
    query = """
    SELECT trade_id, account_name, symbol, entry_time, exit_time, entry_price, exit_price, profit_loss, side
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL' AND (entry_price > 300 OR exit_price > 300)
    LIMIT 20
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    
    # 2. Check max dates for Days Ago calc
    print("\n--- Max Dates TS_4 ---")
    c = conn.cursor()
    c.execute("SELECT MAX(exit_time) FROM processed_trades WHERE account_name='TS_4'")
    max_date = c.fetchone()[0]
    print(f"Max Exit Time DB: {max_date}")
    
    if max_date:
        try:
            last = datetime.fromisoformat(max_date)
            now = datetime.now()
            print(f"Diff: {(now - last).days} days")
        except:
            pass

    conn.close()

if __name__ == "__main__":
    inspect_bad_prices()
