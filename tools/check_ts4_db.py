import sqlite3
import pandas as pd
import os

def check_db():
    db_path = 'trading_platform.db'
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("--- Database Summary for TS_4 ---")
    c.execute("SELECT COUNT(*), SUM(profit_loss), AVG(profit_loss) FROM processed_trades WHERE account_name='TS_4'")
    count, total_pnl, avg_pnl = c.fetchone()
    print(f"Total Trades: {count}")
    print(f"Total PnL: ${total_pnl:,.2f}")
    print(f"Avg PnL: ${avg_pnl:,.2f}")

    print("\n--- First 5 Trades in DB for TS_4 ---")
    c.execute("SELECT entry_time, exit_time, entry_price, exit_price, side, quantity, profit_loss FROM processed_trades WHERE account_name='TS_4' ORDER BY entry_time ASC LIMIT 5")
    for r in c.fetchall():
        print(dict(r))
    
    conn.close()

if __name__ == "__main__":
    check_db()
