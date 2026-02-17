import sqlite3
import pandas as pd

def find_mismatches():
    txt_path = 'C:/SierraChart/CL_TS_4.txt'
    db_path = 'trading_platform.db'

    print("Loading data...")
    df_sc = pd.read_csv(txt_path, sep='\t')
    df_sc['entry_ts'] = pd.to_datetime(df_sc['Entry DateTime'].str.replace(' BP', '').str.replace(' EP', '').str.strip())
    
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT entry_time, profit_loss FROM processed_trades WHERE account_name='TS_4' ORDER BY profit_loss DESC LIMIT 20")
    top_db_trades = c.fetchall()
    
    print("\n--- Top 20 Most Profitable Trades in DB (TS_4) ---")
    for et, pnl in top_db_trades:
        # Check if this entry time exists in SC TXT within a tolerance
        # (DB is ISO, TXT is YYYY-MM-DD  HH:MM:SS)
        exists = "NO"
        try:
            db_ts = pd.to_datetime(et.replace('T', ' '))
            match = df_sc[(df_sc['entry_ts'] >= db_ts - pd.Timedelta(seconds=5)) & (df_sc['entry_ts'] <= db_ts + pd.Timedelta(seconds=5))]
            if len(match) > 0:
                exists = f"YES (SC PnL: {match.iloc[0]['Profit/Loss (C)']})"
        except: pass
        
        print(f"DB Entry: {et} | PnL: ${pnl:,.2f} | Found in SC TXT? {exists}")

    conn.close()

if __name__ == "__main__":
    find_mismatches()
