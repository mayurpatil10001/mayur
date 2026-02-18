import sqlite3
import pandas as pd
import os

def find_offset():
    txt_path = 'CL_TS_4.txt'
    db_path = 'trading_platform.db'
    
    df_sc = pd.read_csv(txt_path, sep='\t')
    df_sc = df_sc[df_sc['Account'].astype(str).str.contains('TS_4', na=False)]
    
    conn = sqlite3.connect(db_path)
    # Get a few trades from SC
    for i in range(5):
        sc_row = df_sc.iloc[i]
        sc_pnl = float(str(sc_row['Profit/Loss (C)']).replace('$', '').replace(',', '').replace('(', '-').replace(')', '').replace('F', '').split(' ')[0])
        sc_price = sc_row['Entry Price']
        sc_time = sc_row['Entry DateTime']
        
        print(f"Searching for SC Trade: Time={sc_time}, Price={sc_price}, PnL={sc_pnl}")
        
        # Search in DB for similar PnL and Price
        # We search with a tolerance for PnL
        query = "SELECT entry_time, entry_price, profit_loss FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL' AND ABS(entry_price - ?) < 0.01 AND ABS(profit_loss - ?) < 0.1 LIMIT 3"
        cursor = conn.execute(query, (sc_price, sc_pnl))
        matches = cursor.fetchall()
        
        for m in matches:
            print(f"  POTENTIAL DB MATCH: Time={m[0]}, Price={m[1]}, PnL={m[2]}")
            
    conn.close()

if __name__ == "__main__":
    find_offset()
