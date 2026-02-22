
import sqlite3
import pandas as pd

def check_trades():
    conn = sqlite3.connect('trading_platform.db')
    query = """
    SELECT account_name, symbol, profit_loss, entry_time 
    FROM processed_trades 
    WHERE entry_time LIKE '2025-11-20%' 
    ORDER BY profit_loss DESC
    """
    df = pd.read_sql_query(query, conn)
    print(f"Total trades on 2025-11-20: {len(df)}")
    print(f"Total PnL for the day (Gross): {df['profit_loss'].sum():.2f}")
    
    nq_trades = df[df['symbol'] == 'NQ']
    print(f"\nNQ Summary:")
    print(f"NQ Trades: {len(nq_trades)}")
    print(f"NQ PnL: {nq_trades['profit_loss'].sum():.2f}")
    print(f"NQ Avg PnL: {nq_trades['profit_loss'].mean():.2f}")
    print(f"NQ StdDev: {nq_trades['profit_loss'].std():.2f}")
    print(f"NQ Max: {nq_trades['profit_loss'].max():.2f}")
    print(f"NQ Min: {nq_trades['profit_loss'].min():.2f}")
    
    print("\nTop 10 NQ trades:")
    print(nq_trades.head(10))
    
    # Check for trades > $10k
    massive = df[df['profit_loss'].abs() > 10000]
    if not massive.empty:
        print("\nMassive trades (> $10k):")
        print(massive)
    else:
        print("\nNo individual trades > $10k found.")
    
    # Check for potential duplicates (same time, account, symbol, pnl)
    duplicates = df.duplicated(subset=['entry_time', 'account_name', 'symbol', 'profit_loss'], keep=False)
    if duplicates.any():
        print(f"\nPotential Duplicates Found: {duplicates.sum()}")
        print(df[duplicates].head(10))
    else:
        print("\nNo exact duplicates found.")
        
    # Check account concentration
    acc_pnl = df.groupby('account_name')['profit_loss'].agg(['sum', 'count']).sort_values(by='sum', ascending=False)
    print("\nPnL by Account:")
    print(acc_pnl.head(15))
    
    # Strategy Activity Check
    strat_activity = df.groupby(['account_name', 'symbol']).size().sort_values(ascending=False)
    print("\nMost Active Strategy-Symbol Pairs:")
    print(strat_activity.head(15))
    
    # Check if TM_7 trades are spread across different symbols
    tm7_detail = df[df['account_name'] == 'TM_7'].groupby('symbol').size()
    print("\nTM_7 Activity by Symbol:")
    print(tm7_detail)

    # Burst Check: Trades per minute for TM_7
    tm7_trades = df[df['account_name'] == 'TM_7'].copy()
    if not tm7_trades.empty:
        tm7_trades['minute'] = tm7_trades['entry_time'].apply(lambda x: x[:16])
        bursts = tm7_trades.groupby('minute').size().sort_values(ascending=False)
        print("\nTM_7 Burst Activity (Trades per minute):")
        print(bursts.head(10))

if __name__ == "__main__":
    check_trades()
