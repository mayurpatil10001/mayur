import sqlite3

def check():
    conn = sqlite3.connect('trading_platform.db')
    cur = conn.cursor()
    
    if 'processed_trades' in (r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()):
        for acc in ['CL_TS_2', 'TS_2']:
            print(f"\nStats for {acc}:")
            cur.execute(f"SELECT MIN(entry_time), MAX(entry_time), COUNT(DISTINCT symbol) FROM processed_trades WHERE account_name = ?", (acc,))
            start, end, sym_count = cur.fetchone()
            print(f"  Range: {start} to {end}")
            print(f"  Symbols: {sym_count}")
            
            cur.execute(f"SELECT symbol, COUNT(1) FROM processed_trades WHERE account_name = ? GROUP BY symbol", (acc,))
            for sym, count in cur.fetchall():
                print(f"    - {sym}: {count} trades")

    conn.close()

if __name__ == "__main__":
    check()
