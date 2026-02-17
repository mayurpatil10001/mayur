import sqlite3
import pandas as pd

def check_cl_pnl():
    conn = sqlite3.connect('trading_platform.db')
    
    query = "SELECT SUM(profit_loss) as total_pnl, COUNT(*) as count FROM processed_trades WHERE account_name='TS_4' AND symbol='CL'"
    df = pd.read_sql_query(query, conn)
    print("--- TS_4 CL Stats ---")
    print(df.to_string())
    
    print("\n--- Recent CL Trades ---")
    df2 = pd.read_sql_query("SELECT * FROM processed_trades WHERE account_name='TS_4' AND symbol='CL' ORDER BY exit_time DESC LIMIT 5", conn)
    print(df2.to_string())

    conn.close()

if __name__ == "__main__":
    check_cl_pnl()
