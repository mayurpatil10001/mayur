import sqlite3
import datetime

DB = 'trading_platform.db'

def sync():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # 1. Clear trades table for accounts that have data in processed_trades
    # (Optional: Only if we want to overwrite)
    # For now let's just insert missing ones.
    
    print("Fetching trades from processed_trades...")
    c.execute("""
        SELECT 
            account_name, symbol, side, quantity, 
            entry_price, exit_price, entry_time, exit_time, 
            profit_loss, commission
        FROM processed_trades
    """)
    rows = c.fetchall()
    print(f"Found {len(rows)} trades to sync.")
    
    count = 0
    for r in rows:
        acc, sym, side, qty, p1, p2, t1, t2, pnl, comm = r
        
        # Mapping: side -> trade_type, quantity -> volume, profit_loss -> net_profit
        # Insert Into trades (id is autoincrement)
        c.execute("""
            INSERT OR IGNORE INTO trades (
                account, symbol, trade_type, volume, 
                entry_price, exit_price, entry_time, exit_time, 
                net_profit, commission, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CLOSED')
        """, (acc, sym, side, qty, p1, p2, t1, t2, pnl, comm))
        if c.rowcount > 0:
            count += 1
            
    conn.commit()
    conn.close()
    print(f"Synchronized {count} new trades to the master 'trades' table.")

if __name__ == "__main__":
    sync()
