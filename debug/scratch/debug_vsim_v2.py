import sqlite3
import datetime

NY_TZ = datetime.timezone(datetime.timedelta(hours=-5)) # Approximation, close enough for EOD rule

def check_all_v_sim():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    
    # 1. Check all account names starting with V_
    print("--- V_ Accounts Found ---")
    c.execute("SELECT DISTINCT account_name FROM processed_trades WHERE account_name LIKE 'V_%'")
    accounts = [r[0] for r in c.fetchall()]
    print(accounts)
    
    for acc in accounts:
        print(f"\n--- Account: {acc} ---")
        c.execute(f"SELECT date(entry_time), count(*), sum(profit_loss) FROM processed_trades WHERE account_name = ? AND entry_time LIKE '2025-11%' GROUP BY 1", (acc,))
        rows = c.fetchall()
        if not rows:
            print("No data in Nov 2025")
        for r in rows:
            print(f"Date: {r[0]}, Trades: {r[1]}, PnL: {r[2]}")

    print("\n--- Note Analysis for V_SIM16 on 2025-11-27 ---")
    # We don't store notes in processed_trades usually, but we can check pending_fills
    c.execute("SELECT created_at, side, quantity, symbol FROM pending_fills WHERE account_name = 'V_SIM16' LIMIT 10")
    rows = c.fetchall()
    print("Pending Fills sampled:")
    for r in rows:
        print(r)

    conn.close()

if __name__ == "__main__":
    check_all_v_sim()
