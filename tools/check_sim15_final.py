
import sqlite3

def check_sim15_totals():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("""
        SELECT 
            COUNT(*) as trade_count,
            SUM(quantity) as total_qty,
            SUM(profit_loss) as net_pnl,
            SUM(commission) as total_comm
        FROM processed_trades 
        WHERE account_name = '3Q_SIM15'
    """)
    res = c.fetchone()
    print("\n--- Final Database Status for 3Q_SIM15 ---")
    if res and res[0] > 0:
        print(f"Trade Count: {res[0]}")
        print(f"Total Quantity: {res[1]}")
        print(f"Total Commissions: ${res[3]:.2f}")
        print(f"Net PnL: ${res[2]:.2f}")
    else:
        print("No trades found.")
    conn.close()

if __name__ == "__main__":
    check_sim15_totals()
