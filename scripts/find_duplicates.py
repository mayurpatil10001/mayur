
import sqlite3
import pandas as pd

def find_all_duplicates():
    conn = sqlite3.connect('trading_platform.db')
    # Use a chunked approach if table is very large, but let's try direct first
    query = """
    SELECT entry_time, account_name, symbol, profit_loss, COUNT(*) as count
    FROM processed_trades
    GROUP BY entry_time, account_name, symbol, profit_loss
    HAVING COUNT(*) > 1
    """
    df = pd.read_sql_query(query, conn)
    print(f"Total Unique Sets of Duplicates: {len(df)}")
    print(f"Total Extra Trade Rows: {df['count'].sum() - len(df)}")
    
    if not df.empty:
        print("\nTop duplicate sets:")
        print(df.sort_values(by='count', ascending=False).head(10))
    
    conn.close()

if __name__ == "__main__":
    find_all_duplicates()
