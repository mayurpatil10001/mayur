import sqlite3
import os

def check_symbols():
    db_path = 'trading_platform.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT symbol, COUNT(*) FROM processed_trades WHERE account_name='TS_4' GROUP BY symbol")
    rows = c.fetchall()
    print("--- TS_4 Trades by Symbol ---")
    for sym, count in rows:
        print(f"{sym}: {count} trades")
    conn.close()

if __name__ == "__main__":
    check_symbols()
