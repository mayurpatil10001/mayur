import sqlite3
import pandas as pd

def check_durations():
    conn = sqlite3.connect('trading_platform.db')
    
    print("--- Trade Duration Stats (Minutes) ---")
    query = """
    SELECT AVG(duration_minutes), MAX(duration_minutes), MIN(duration_minutes)
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL'
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    
    print("\n--- Longest Duration Trades ---")
    query_long = """
    SELECT trade_id, entry_time, exit_time, duration_minutes, profit_loss 
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL' 
    ORDER BY duration_minutes DESC 
    LIMIT 20
    """
    df_long = pd.read_sql_query(query_long, conn)
    print(df_long.to_string())

    conn.close()

if __name__ == "__main__":
    check_durations()
