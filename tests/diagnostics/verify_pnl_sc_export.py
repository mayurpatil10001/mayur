import pandas as pd
import numpy as np

def verify_sc_export(filepath):
    print(f"Reading {filepath}...")
    try:
        df = pd.read_csv(filepath, sep='\t', low_memory=False)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Filter for 'Fills' only
    if 'ActivityType' not in df.columns:
        print("Column 'ActivityType' not found. Columns:", df.columns)
        return

    fails_df = df[df['ActivityType'].astype(str).str.contains('Fill', case=False, na=False)]
    print(f"Total Fills lines: {len(fails_df)}")

    # Filter for Symbol 'CL'
    if 'Symbol' in df.columns:
        cl_fills = fails_df[fails_df['Symbol'].astype(str).str.startswith('CL')]
    else:
        print("Symbol column not found.")
        return

    print(f"CL Fills count: {len(cl_fills)}")

    multiplier = 1000.0
    
    df_pnl = cl_fills.copy()
    if 'DateTime' in df_pnl.columns:
        df_pnl['dt'] = pd.to_datetime(df_pnl['DateTime'].str[:19], errors='coerce')
    else:
        print("DateTime column missing")
        return

    df_pnl['pnl'] = 0.0
    
    for index, row in df_pnl.iterrows():
        try:
            price = float(row['FillPrice'])
            qty = float(row['FilledQuantity'])
            side = str(row['BuySell']).lower()
            
            val = 0.0
            if 'buy' in side:
                val = -price * qty * multiplier
            elif 'sell' in side:
                val = price * qty * multiplier
            
            df_pnl.at[index, 'pnl'] = val
                
        except Exception as e:
            pass

    total_pnl = df_pnl['pnl'].sum()
    
    buy_qty = df_pnl[df_pnl['BuySell'].astype(str).str.contains('Buy', case=False, na=False)]['FilledQuantity'].sum()
    sell_qty = df_pnl[df_pnl['BuySell'].astype(str).str.contains('Sell', case=False, na=False)]['FilledQuantity'].sum()
    
    print("-" * 30)
    print(f"Date Range: {df_pnl['dt'].min()} to {df_pnl['dt'].max()}")
    print(f"Total CL Fills: {len(cl_fills)}")
    print(f"Total Buy Qty: {buy_qty}")
    print(f"Total Sell Qty: {sell_qty}")
    print(f"Net Qty: {sell_qty - buy_qty}")
    print(f"Estimated GROSS PnL (from Fills): ${total_pnl:,.2f}")
    
    # Daily PnL
    df_pnl['date'] = df_pnl['dt'].dt.date
    daily = df_pnl.groupby('date')['pnl'].sum().sort_index()
    print("\nTop 5 Best Days:")
    print(daily.nlargest(5))
    print("\nTop 5 Worst Days:")
    print(daily.nsmallest(5))
    
    print("-" * 30)
    
    # Account Balance Check
    print("Checking Account Balance...")
    if 'AccountBalance' in df.columns:
        # Sort by DateTime
        # We use the full DF, not just fills, to capture all balance updates
        acc_df = df.copy()
        acc_df['dt'] = pd.to_datetime(acc_df['DateTime'].str[:19], errors='coerce')
        acc_df = acc_df.sort_values('dt')
        
        # Get valid balances (non-zero, non-NaN)
        # Assuming AccountBalance column is numeric
        # SC sometimes puts garbage? Let's clean.
        acc_df['AccountBalance'] = pd.to_numeric(acc_df['AccountBalance'], errors='coerce')
        valid_bals = acc_df[acc_df['AccountBalance'] > 0]['AccountBalance']
        
        if not valid_bals.empty:
            start_bal = valid_bals.iloc[0]
            end_bal = valid_bals.iloc[-1]
            diff = end_bal - start_bal
            print(f"First Balance Record: {acc_df.iloc[valid_bals.index[0]]['dt']} : {start_bal:,.2f}")
            print(f"Last Balance Record:  {acc_df.iloc[valid_bals.index[-1]]['dt']} : {end_bal:,.2f}")
            print(f"Balance Diff (Net PnL?): ${diff:,.2f}")
        else:
            print("No valid AccountBalance found.")
    else:
        print("AccountBalance column missing.")

if __name__ == "__main__":
    file_path = r"C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt"
    verify_sc_export(file_path)
