import sqlite3
import pandas as pd

def check_cl_dates():
    conn = sqlite3.connect('trading_platform.db')
    
    print("--- CL Date Range ---")
    query = """
    SELECT MIN(entry_time), MAX(entry_time), AVG(profit_loss), SUM(profit_loss)
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL'
    """
    df = pd.read_sql_query(query, conn)
    print(df.to_string())
    
    print("\n--- CL Monthly PnL ---")
    query_monthly = """
    SELECT strftime('%Y-%m', entry_time) as month, COUNT(*) as count, SUM(profit_loss) as pnl
    FROM processed_trades 
    WHERE account_name='TS_4' AND symbol='CL'
    GROUP BY month
    ORDER BY month
    """
    df_monthly = pd.read_sql_query(query_monthly, conn)
    print(df_monthly.to_string())

    conn.close()

if __name__ == "__main__":
    check_cl_dates()
