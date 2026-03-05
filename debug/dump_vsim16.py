import sqlite3

def dump():
    conn = sqlite3.connect('trading_platform.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT entry_time, exit_time, entry_price, exit_price, quantity, profit_loss 
        FROM processed_trades 
        WHERE account_name = 'V_sim16' 
        AND entry_time LIKE '2025-12-18%' 
        ORDER BY entry_time ASC
    """)
    rows = c.fetchall()
    with open('debug/v_sim16_check.txt', 'w') as f:
        f.write(f"V_sim16 trades on 2025-12-18 - Total: {len(rows)}\n\n")
        f.write(f"{'Entry Time':<30} | {'Exit Time':<30} | {'Price In':<10} | {'Price Out':<10} | {'Qty':<3} | {'PnL':<10}\n")
        f.write("-" * 120 + "\n")
        for r in rows:
            f.write(f"{r['entry_time']:<30} | {r['exit_time']:<30} | {r['entry_price']:<10} | {r['exit_price']:<10} | {r['quantity']:<3} | {r['profit_loss']:<10.2f}\n")
    conn.close()

if __name__ == "__main__":
    dump()
