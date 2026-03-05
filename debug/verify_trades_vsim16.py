import sqlite3
import json

def check_trades():
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("Checking Account: V_SIM16 on 2025-12-18\n")
    
    # Query for the specific day
    c.execute("""
        SELECT trade_id, entry_time, exit_time, entry_price, exit_price, quantity, profit_loss, symbol
        FROM processed_trades 
        WHERE account_name = 'V_SIM16' 
        AND entry_time LIKE '2025-12-18%' 
        ORDER BY entry_time
    """)
    
    rows = c.fetchall()
    print(f"Total trades found for that day: {len(rows)}\n")
    
    print(f"{'Entry Time':<25} | {'Exit Time':<25} | {'Qty':<3} | {'PnL':<10}")
    print("-" * 75)
    
    for r in rows[:15]:
        print(f"{r['entry_time']:<25} | {r['exit_time']:<25} | {r['quantity']:<3} | {r['profit_loss']:<10.2f}")
        
    conn.close()

if __name__ == "__main__":
    check_trades()
