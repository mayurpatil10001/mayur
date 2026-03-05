import sqlite3

def check_trades():
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("Checking Account: V_sim16 on 2025-12-18\n")
    
    # Query for the specific day - using exact casing V_sim16
    c.execute("""
        SELECT entry_time, exit_time, entry_price, exit_price, quantity, profit_loss 
        FROM processed_trades 
        WHERE account_name = 'V_sim16' 
        AND entry_time LIKE '2025-12-18%' 
        ORDER BY entry_time ASC
    """)
    
    rows = c.fetchall()
    print(f"Total trades found: {len(rows)}\n")
    
    print(f"{'#':<3} | {'Entry Time':<25} | {'Exit Time':<25} | {'Qty':<3} | {'PnL':<10}")
    print("-" * 80)
    
    for i, r in enumerate(rows[:20], 1):
        print(f"{i:<3} | {r['entry_time']:<25} | {r['exit_time']:<25} | {r['quantity']:<3} | {r['profit_loss']:<10.2f}")
        
    conn.close()

if __name__ == "__main__":
    check_trades()
