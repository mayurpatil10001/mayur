
import sqlite3

def check_all():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    accounts = ['3Q_SIM13', '3Q_SIM14', '3Q_SIM15']
    print("\n--- FINAL GLOBAL RECONCILIATION ---")
    for acc in accounts:
        c.execute("""
            SELECT COUNT(*), SUM(quantity), SUM(profit_loss), SUM(commission)
            FROM processed_trades WHERE account_name = ?
        """, (acc,))
        res = c.fetchone()
        if res and res[0]:
            print(f"{acc}: {res[0]} trades, Qty: {res[1]}, PnL: ${res[2]:.2f}, Comm: ${res[3]:.2f}")
    conn.close()

if __name__ == "__main__":
    check_all()
