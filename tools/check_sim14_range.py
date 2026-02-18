
import sqlite3
import json

def check_range():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    
    print("Account: 3Q_SIM14")
    c.execute("SELECT MIN(entry_time), MAX(entry_time), COUNT(*), SUM(profit_loss) FROM processed_trades WHERE account_name = '3Q_SIM14'")
    res = c.fetchone()
    print(f"Added Trades: Min: {res[0]}, Max: {res[1]}, Count: {res[2]}, PnL: {res[3]}")
    
    # Check dropped trades if we had a log of them or if we can see gaps
    # But dropped trades are NOT in the DB.
    
    # Let's check the date range for all trades in SIM14 to see if we are missing 2024.
    
    print("\nYearly Breakdown for 3Q_SIM14:")
    c.execute("""
        SELECT strftime('%Y', entry_time) as year, COUNT(*), SUM(profit_loss)
        FROM processed_trades 
        WHERE account_name = '3Q_SIM14'
        GROUP BY year
        ORDER BY year
    """)
    for row in c.fetchall():
        print(f"Year {row[0]}: {row[1]} trades, ${row[2]:.2f} PnL")

    conn.close()

if __name__ == "__main__":
    check_range()
