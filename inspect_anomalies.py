import sqlite3
import pandas as pd

def inspect_anomalies():
    conn = sqlite3.connect('trading_platform.db')
    
    # Check for extreme PnL trades
    print("--- Top 10 Worst PnL Trades ---")
    query = """
    SELECT entry_time, exit_time, symbol, side, entry_price, exit_price, quantity, net_profit 
    FROM processed_trades 
    WHERE account = 'TS_4' 
    ORDER BY net_profit ASC 
    LIMIT 10
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())

    # Check for most recent trade
    print("\n--- Most Recent Trades ---")
    query_recent = """
    SELECT entry_time, exit_time, symbol, side, net_profit 
    FROM processed_trades 
    WHERE account = 'TS_4' 
    ORDER BY exit_time DESC 
    LIMIT 10
    """
    df_recent = pd.read_sql_query(query_recent, conn)
    print(df_recent.to_string())

    conn.close()

if __name__ == "__main__":
    inspect_anomalies()
