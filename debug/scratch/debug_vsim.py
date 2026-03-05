import sqlite3
import json

def check_vsim16_data():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    
    print("--- V_SIM16 Trades in Nov 2025 ---")
    c.execute("SELECT date(entry_time), count(*), sum(profit_loss) FROM processed_trades WHERE account_name = 'V_SIM16' AND entry_time LIKE '2025-11%' GROUP BY 1")
    rows = c.fetchall()
    for r in rows:
        print(f"Date: {r[0]}, Count: {r[1]}, PnL: {r[2]}")
        
    print("\n--- Sample Trades on 2025-11-05 ---")
    c.execute("SELECT entry_time, side, quantity, profit_loss FROM processed_trades WHERE account_name = 'V_SIM16' AND date(entry_time) = '2025-11-05' LIMIT 5")
    rows = c.fetchall()
    for r in rows:
        print(r)

    print("\n--- Sample Trades on 2025-11-06 ---")
    c.execute("SELECT entry_time, side, quantity, profit_loss FROM processed_trades WHERE account_name = 'V_SIM16' AND date(entry_time) = '2025-11-06' LIMIT 5")
    rows = c.fetchall()
    for r in rows:
        print(r)

    conn.close()

if __name__ == "__main__":
    check_vsim16_data()
