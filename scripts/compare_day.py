import sqlite3
import pandas as pd

def compare_day():
    txt_path = 'C:/SierraChart/CL_TS_4.txt'
    db_path = 'trading_platform.db'
    target_day = "2024-11-18"

    print(f"--- Comparison for {target_day} ---")
    
    # SC TXT
    df_sc = pd.read_csv(txt_path, sep='\t')
    df_sc = df_sc[df_sc['Entry DateTime'].str.startswith(target_day)]
    df_sc = df_sc[df_sc['Account'].astype(str).str.contains('TS_4')]
    
    print(f"SC (TXT) Trades on {target_day}: {len(df_sc)}")
    for _, row in df_sc.head(5).iterrows():
        print(f"SC: {row['Entry DateTime']} | {row['Trade Type']} | {row['Entry Price']} -> {row['Exit Price']} | Qty: {row['Trade Quantity']} | PnL: {row['Profit/Loss (C)']}")

    # Platform DB
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(f"SELECT entry_time, exit_time, side, entry_price, exit_price, quantity, profit_loss FROM processed_trades WHERE account_name='TS_4' AND entry_time LIKE '{target_day}%' ORDER BY entry_time ASC")
    rows = c.fetchall()
    
    print(f"\nPlatform DB Trades on {target_day}: {len(rows)}")
    for r in rows[:5]:
        print(f"DB: {r['entry_time']} | {r['side']} | {r['entry_price']} -> {r['exit_price']} | Qty: {r['quantity']} | PnL: {r['profit_loss']}")

    conn.close()

if __name__ == "__main__":
    compare_day()
