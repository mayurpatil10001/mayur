import sqlite3
import pandas as pd

def inspect_long_trades():
    conn = sqlite3.connect('trading_platform.db')
    
    print("--- Trades Duration > 5 Days ---")
    query = """
    SELECT trade_id, account_name, symbol, entry_time, exit_time, duration_minutes, profit_loss
    FROM processed_trades 
    WHERE account_name='TS_4' AND duration_minutes > 7200
    ORDER BY duration_minutes DESC
    LIMIT 10
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    
    conn.close()

if __name__ == "__main__":
    inspect_long_trades()
