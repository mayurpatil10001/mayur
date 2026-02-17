import sqlite3
import pandas as pd
import os

def compare_day():
    txt_path = 'C:/SierraChart/CL_TS_4.txt'
    db_path = 'trading_platform.db'
    target_day = "2024-11-18"

    print(f"--- Comparison for {target_day} ---")
    
    # SC TXT
    try:
        df_sc_full = pd.read_csv(txt_path, sep='\t')
        # Filter for TS_4 and Date
        df_sc = df_sc_full[df_sc_full['Entry DateTime'].astype(str).str.contains(target_day, na=False)].copy()
        df_sc = df_sc[df_sc['Account'].astype(str).str.contains('TS_4', na=False)].copy()
    except Exception as e:
        print(f"SC Read Error: {e}")
        return
    
    print(f"SC (TXT) Trades on {target_day}: {len(df_sc)}")
    for _, row in df_sc.head(5).iterrows():
        # Get numeric PnL
        pnl_raw = str(row['Profit/Loss (C)']).replace('$', '').replace(',', '')
        print(f"SC: {row['Entry DateTime']} | {row['Trade Type']} | {row['Entry Price']} -> {row['Exit Price']} | Qty: {row['Trade Quantity']} | PnL: {pnl_raw}")

    # Platform DB
    if not os.path.exists(db_path):
        print("DB Not Found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Note: SQL LIKE for T separators
    query = f"SELECT entry_time, side, entry_price, exit_price, quantity, profit_loss FROM processed_trades WHERE account_name='TS_4' AND entry_time LIKE '{target_day}%' ORDER BY entry_time ASC"
    c.execute(query)
    db_rows = c.fetchall()
    
    print(f"\nPlatform DB Trades on {target_day}: {len(db_rows)}")
    for r in db_rows[:5]:
        print(f"DB: {r['entry_time']} | {r['side']} | {r['entry_price']} -> {r['exit_price']} | Qty: {r['quantity']} | PnL: {r['profit_loss']}")

    # Check for CONTRACT MULTIPLIER discrepancy
    if len(df_sc) > 0 and len(db_rows) > 0:
        # Example math for first trade
        sc_row = df_sc.iloc[0]
        db_row = db_rows[0]
        
        print("\n--- Match Analysis (First Trade of Day) ---")
        print(f"SC: Side={sc_row['Trade Type']}, Entry={sc_row['Entry Price']}, Exit={sc_row['Exit Price']}, Qty={sc_row['Trade Quantity']}, PnL={sc_row['Profit/Loss (C)']}")
        
        # Calculate expected PnL with standard CL multiplier (1000)
        # Entry 66.66 -> Exit 66.71 Short?
        try:
            entry = float(sc_row['Entry Price'])
            exit = float(sc_row['Exit Price'])
            qty = float(sc_row['Trade Quantity'])
            side = str(sc_row['Trade Type']).upper()
            
            pnl_points = (entry - exit) if 'SHORT' in side else (exit - entry)
            pnl_gross = pnl_points * 1000 * qty
            print(f"Calculated Gross PnL (Standard CL 1000x): {pnl_gross:,.2f}")
            comm = 4.2 * qty
            print(f"Calculated Net PnL (Minus {comm:,.2f} comm): {(pnl_gross - comm):,.2f}")
        except:
            pass

    conn.close()

if __name__ == "__main__":
    compare_day()
