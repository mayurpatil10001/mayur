import sqlite3
import pandas as pd

def check_specific_trade():
    conn = sqlite3.connect('trading_platform.db')
    
    # Target: CLZ25 Short on 2025-11-17
    # Note: In DB symbol is CL (Base), but dates match.
    target_date = '2025-11-17'
    
    print(f"--- Looking for trades on {target_date} ---")
    query = f"""
    SELECT trade_id, account_name, symbol, side, entry_time, exit_time, entry_price, exit_price, quantity, profit_loss
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL' AND entry_time LIKE '{target_date}%'
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    
    conn.close()

if __name__ == "__main__":
    check_specific_trade()
