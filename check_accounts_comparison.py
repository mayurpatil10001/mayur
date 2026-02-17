import sqlite3

def check():
    conn = sqlite3.connect('trading_platform.db')
    cur = conn.cursor()
    
    # 1. List tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    # 2. Check accounts in processed_trades
    if 'processed_trades' in tables:
        print("\nSymbol breakdown for CL_TS_2:")
        cur.execute("SELECT symbol, COUNT(1) FROM processed_trades WHERE account_name = 'CL_TS_2' GROUP BY symbol")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
            
        print("\nSymbol breakdown for TS_2:")
        cur.execute("SELECT symbol, COUNT(1) FROM processed_trades WHERE account_name = 'TS_2' GROUP BY symbol")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
            
        # 3. Check if they have the same trades (overlap)
        print("\nChecking for trade overlap (entry_time, side, quantity, symbol):")
        cur.execute("""
            SELECT count(1) FROM (
                SELECT symbol, entry_time, side, quantity FROM processed_trades WHERE account_name = 'CL_TS_2'
                INTERSECT
                SELECT symbol, entry_time, side, quantity FROM processed_trades WHERE account_name = 'TS_2'
            )
        """)
        overlap = cur.fetchone()[0]
        print(f"  Intersection count: {overlap}")
        
    conn.close()

if __name__ == "__main__":
    check()
