import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime

def analyze_account(account_name, slot=None, dow=None):
    conn = sqlite3.connect('trading_platform.db')
    query = f"SELECT * FROM processed_trades WHERE account_name = '{account_name}'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print(f"No trades found for {account_name}")
        return

    df['entry_time'] = pd.to_datetime(df['entry_time'], format='mixed')
    
    # Extract slot and dow
    df['time_slot'] = df['entry_time'].apply(lambda dt: f"{dt.hour:02d}:{0 if dt.minute < 30 else 30:02d}")
    df['dow'] = df['entry_time'].dt.dayofweek # 0=Mon, 6=Sun
    
    if slot:
        df = df[df['time_slot'] == slot]
    if dow is not None:
        df = df[df['dow'] == dow]

    df = df.sort_values('entry_time')
    
    if df.empty:
        print(f"No trades found for {account_name} at {slot} dow={dow}")
        return
    
    # ... rest of stats ...
    total_pnl = df['profit_loss'].sum()
    trades = len(df)
    winners = df[df['profit_loss'] > 0]
    losers = df[df['profit_loss'] <= 0]
    
    win_rate = (len(winners) / trades) * 100 if trades > 0 else 0
    avg_win = winners['profit_loss'].mean()
    avg_loss = losers['profit_loss'].mean()
    
    profit_factor = winners['profit_loss'].sum() / abs(losers['profit_loss'].sum()) if not losers.empty else float('inf')
    
    df['year_month'] = df['entry_time'].dt.strftime('%Y-%m')
    monthly = df.groupby('year_month')['profit_loss'].sum()
    profitable_months = (monthly > 0).sum()
    total_months = len(monthly)
    persistence = (profitable_months / total_months) * 100
    
    print(f"--- Analysis for {account_name} [{slot} Day={dow}] ---")
    print(f"Total PnL: ${total_pnl:,.2f}")
    print(f"Total Trades: {trades}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Profit Factor: {profit_factor:.2f}")
    print(f"Monthly Persistence: {persistence:.2f}% ({profitable_months}/{total_months} months)")

if __name__ == "__main__":
    analyze_account('V_sim16', '09:30', 0) # Mon 09:30
