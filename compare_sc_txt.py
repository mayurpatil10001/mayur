import sqlite3
import pandas as pd
import numpy as np

def compare():
    txt_path = 'C:/SierraChart/CL_TS_4.txt'
    db_path = 'trading_platform.db'
    
    # Read the TXT file trades
    print(f"Reading SC TXT: {txt_path}...")
    try:
        df_sc = pd.read_csv(txt_path, sep='\t')
    except Exception as e:
        print(f"Error reading SC CSV: {e}")
        return

    # Clean PnL column (it might have currency symbols or commas)
    if 'Profit/Loss (C)' in df_sc.columns:
        # Convert to string first to handle any mixed types
        pnl_col = df_sc['Profit/Loss (C)'].astype(str)
        # Remove '$', '(', ')', ',' and handle negative (often (123.45) in finance)
        pnl_col = pnl_col.str.replace('$', '').str.replace(',', '')
        # Handle parentheses for negatives
        pnl_col = pnl_col.apply(lambda x: '-' + x.replace('(','').replace(')','') if '(' in x else x)
        # Try to convert to float
        df_sc['pnl_clean'] = pd.to_numeric(pnl_col.str.extract('([-+]?\d*\.\d+|\d+)')[0], errors='coerce')
    
    # Filter for Account TS_4
    if 'Account' in df_sc.columns:
        df_sc = df_sc[df_sc['Account'].astype(str).str.contains('TS_4', na=False)]
    
    sc_total_pnl = df_sc['pnl_clean'].sum()
    sc_count = len(df_sc)
    
    print(f"SC TXT Stats (Parsed): Count={sc_count}, Total PnL=${sc_total_pnl:,.2f}")
    
    # Connect to DB
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Range check
    c.execute("SELECT MIN(entry_time), MAX(entry_time) FROM processed_trades WHERE account_name='TS_4'")
    db_min, db_max = c.fetchone()
    print(f"DB Range for TS_4: {db_min} to {db_max}")
    
    if sc_count > 0:
        sc_start = df_sc['Entry DateTime'].min()
        print(f"SC TXT Range: {sc_start} to {df_sc['Entry DateTime'].max()}")
        
        # Filter DB to match SC range
        limit_date = str(sc_start)[:10] + " 00:00:00"
        c.execute("SELECT COUNT(*), SUM(profit_loss) FROM processed_trades WHERE account_name='TS_4' AND entry_time >= ?", (limit_date,))
        db_match_count, db_match_pnl = c.fetchone()
        
        print(f"\n--- MATCHING PERIOD COMPARISON (>= {limit_date}) ---")
        print(f"SC TXT:       Count={sc_count}, PnL=${sc_total_pnl:,.2f}")
        print(f"DB Platform:  Count={db_match_count if db_match_count else 0}, PnL=${db_match_pnl if db_match_pnl else 0:,.2f}")
    else:
        print("No SC trades found for filtering.")

    conn.close()

if __name__ == "__main__":
    compare()
