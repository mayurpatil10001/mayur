import sqlite3

def find_trades_anywhere():
    conn = sqlite3.connect('trading_platform.db')
    c = conn.cursor()
    
    print("--- Searching for any trade on 2025-11-05 ---")
    c.execute("SELECT account_name, symbol, count(*), sum(profit_loss) FROM processed_trades WHERE date(entry_time) = '2025-11-05' GROUP BY 1, 2")
    rows = c.fetchall()
    if not rows:
        print("Absolutely no trades found in DB for 2025-11-05.")
    for r in rows:
        print(f"Acc: {r[0]}, Sym: {r[1]}, Trades: {r[2]}, PnL: {r[3]}")

    print("\n--- Searching for any trade on 2025-11-06 ---")
    c.execute("SELECT account_name, symbol, count(*), sum(profit_loss) FROM processed_trades WHERE date(entry_time) = '2025-11-06' GROUP BY 1, 2")
    rows = c.fetchall()
    if not rows:
        print("Absolutely no trades found in DB for 2025-11-06.")
    for r in rows:
        print(f"Acc: {r[0]}, Sym: {r[1]}, Trades: {r[2]}, PnL: {r[3]}")

    print("\n--- Daily Trade Volume Nov 2025 (Top 10 days) ---")
    c.execute("SELECT date(entry_time), count(*) FROM processed_trades WHERE entry_time LIKE '2025-11%' GROUP BY 1 ORDER BY 1 ASC")
    rows = c.fetchall()
    for r in rows:
        print(f"Date: {r[0]}, Trades: {r[1]}")

    conn.close()

if __name__ == "__main__":
    find_trades_anywhere()
