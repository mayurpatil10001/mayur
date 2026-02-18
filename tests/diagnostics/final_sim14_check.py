
import sqlite3

def final_db_check():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    
    # Check SIM14 totals
    c.execute("""
        SELECT 
            COUNT(*) as trade_count,
            SUM(quantity) as total_qty,
            SUM(profit_loss) as net_pnl,
            SUM(commission) as total_comm
        FROM processed_trades 
        WHERE account_name = '3Q_SIM14'
    """)
    res = c.fetchone()
    
    print("\n--- Final Database Status for 3Q_SIM14 ---")
    if res and res[0] > 0:
        print(f"Trade Count: {res[0]}")
        print(f"Total Quantity: {res[1]}")
        print(f"Total Commissions: ${res[3]:.2f}")
        print(f"Net PnL: ${res[2]:.2f}")
    else:
        print("No trades found (Import might still be running).")

    # Check Yearly distribution
    c.execute("""
        SELECT strftime('%Y', entry_time) as year, COUNT(*), SUM(profit_loss)
        FROM processed_trades 
        WHERE account_name = '3Q_SIM14'
        GROUP BY year
    """)
    print("\nYearly Breakdown:")
    for row in c.fetchall():
        print(f"  {row[0]}: {row[1]} trades, PnL: ${row[2]:.2f}")

    conn.close()

if __name__ == "__main__":
    final_db_check()
