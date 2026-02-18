
import sqlite3

def check():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT symbol FROM processed_trades WHERE account_name = '3Q_SIM14'")
    symbols = [r[0] for r in c.fetchall()]
    print(f"Symbols found in DB for SIM14: {symbols}")
    
    # Check counts per symbol
    for sym in symbols:
        c.execute("SELECT COUNT(*), SUM(profit_loss) FROM processed_trades WHERE account_name = '3Q_SIM14' AND symbol = ?", (sym,))
        res = c.fetchone()
        print(f"  {sym}: {res[0]} trades, ${res[1]:.2f}")
    
    conn.close()

if __name__ == "__main__":
    check()
