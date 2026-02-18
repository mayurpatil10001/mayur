
import sqlite3
import pandas as pd
from datetime import datetime, timedelta

def analyze_binning():
    conn = sqlite3.connect('trading_platform.db')
    
    # Load all trades
    df = pd.read_sql_query("SELECT * FROM processed_trades WHERE symbol='CL'", conn)
    conn.close()
    
    if df.empty:
        print("No trades found.")
        return

    # Convert times to datetime
    df['entry_time'] = pd.to_datetime(df['entry_time'], errors='coerce')
    df['exit_time'] = pd.to_datetime(df['exit_time'], errors='coerce')
    df['profit_loss'] = pd.to_numeric(df['profit_loss'])
    
    # Method 1: Entry Time Binning (Current)
    df['entry_hour'] = df['entry_time'].dt.floor('h')
    entry_pnl = df.groupby('entry_hour')['profit_loss'].sum()
    
    # Method 2: Exit Time Binning
    df['exit_hour'] = df['exit_time'].dt.floor('h')
    exit_pnl = df.groupby('exit_hour')['profit_loss'].sum()
    
    # Method 3: Pro-rated (Split across hours)
    # This is complex, simplified version: 
    # If trade spans multiple hours, split PnL equally? OR by time spent?
    # Let's just compare Entry vs Exit first.
    
    print(f"Comparing Binning Methods for {len(df)} trades:\n")
    
    # Join the two series
    comparison = pd.concat([entry_pnl, exit_pnl], axis=1, keys=['Entry_Based_PnL', 'Exit_Based_PnL']).fillna(0)
    comparison['Diff'] = comparison['Entry_Based_PnL'] - comparison['Exit_Based_PnL']
    
    # Filter for significant differences
    significant_diffs = comparison[abs(comparison['Diff']) > 100].sort_values(by='Diff', key=abs, ascending=False)
    
    print("Top 20 Hours with Significant PnL Differences (Entry vs Exit):")
    print(significant_diffs.head(20))
    
    # Overall stats
    print("\nSummary:")
    print(f"Total PnL (Entry): ${entry_pnl.sum():,.2f}")
    print(f"Total PnL (Exit):  ${exit_pnl.sum():,.2f}") # Should be identical
    
    # Check for trades crossing hour boundary
    df['crosses_hour'] = df['entry_hour'] != df['exit_hour']
    crossing_trades = df[df['crosses_hour']]
    
    print(f"\nTrades crossing hour boundary: {len(crossing_trades)} ({len(crossing_trades)/len(df)*100:.1f}%)")
    if not crossing_trades.empty:
        print("Sample crossing trades:")
        print(crossing_trades[['entry_time', 'exit_time', 'profit_loss']].head())

if __name__ == "__main__":
    analyze_binning()
