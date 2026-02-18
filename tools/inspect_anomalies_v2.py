import sqlite3
import pandas as pd

def inspect_anomalies():
    conn = sqlite3.connect('trading_platform.db')
    
    # Check for extreme PnL trades
    print("--- Top 10 worst PnL Trades ---")
    query = """
    SELECT entry_time, exit_time, symbol, side, entry_price, exit_price, quantity, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'TS_4' 
    ORDER BY profit_loss ASC 
    LIMIT 10
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())

    # Check for most recent trade
    print("\n--- Most Recent 10 Trades ---")
    query_recent = """
    SELECT entry_time, exit_time, symbol, side, profit_loss 
    FROM processed_trades 
    WHERE account_name = 'TS_4' 
    ORDER BY exit_time DESC 
    LIMIT 10
    """
    df_recent = pd.read_sql_query(query_recent, conn)
    print(df_recent.to_string())

    conn.close()

if __name__ == "__main__":
    inspect_anomalies()
