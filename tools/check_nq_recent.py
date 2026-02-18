import sqlite3
import pandas as pd

def check_nq_activity():
    conn = sqlite3.connect('trading_platform.db')
    
    print("--- Recent NQ Trades (Last 10) ---")
    query = """
    SELECT entry_time, exit_time, symbol, side, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'TS_4' AND symbol = 'NQ' 
    ORDER BY exit_time DESC 
    LIMIT 10
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    
    conn.close()

if __name__ == "__main__":
    check_nq_activity()
