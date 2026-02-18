import sqlite3
import pandas as pd

def check_one_trade():
    conn = sqlite3.connect('trading_platform.db')
    
    # Check specific trade 'Te9e1aea01521' or similar recent ones
    query = """
    SELECT trade_id, account_name, symbol, entry_time, exit_time, entry_price, exit_price, quantity, profit_loss, duration_minutes
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL'
    ORDER BY duration_minutes DESC
    LIMIT 1
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())

    conn.close()

if __name__ == "__main__":
    check_one_trade()
