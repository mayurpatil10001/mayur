import sqlite3
import pandas as pd
import os

def count_overall():
    db_path = 'trading_platform.db'
    txt_path = 'CL_TS_4.txt'
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM processed_trades WHERE account_name = 'TS_4' AND symbol = 'CL'")
    db_count = cur.fetchone()[0]
    conn.close()
    
    df_sc = pd.read_csv(txt_path, sep='\t')
    df_sc = df_sc[df_sc['Account'].astype(str).str.contains('TS_4', na=False)]
    sc_count = len(df_sc)
    
    print(f"DB Total CL TS_4: {db_count}")
    print(f"SC Total TS_4:    {sc_count}")
    print(f"Match: {min(db_count, sc_count) / max(db_count, sc_count) * 100:.2f}%")

if __name__ == "__main__":
    count_overall()
