import sqlite3
import time

DB = "trading_platform.db"

def profile_queries():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    print("--- Row Counts ---")
    c.execute("SELECT COUNT(*) FROM processed_trades")
    print(f"processed_trades: {c.fetchone()[0]:,}")
    
    try:
        c.execute("SELECT COUNT(*) FROM temporal_performance")
        print(f"temporal_performance: {c.fetchone()[0]:,}")
    except:
        print("temporal_performance table not found.")

    print("\n--- Profiling Dashboard Query (Stats part) ---")
    start = time.time()
    c.execute("SELECT account_name, symbol, COUNT(*) FROM processed_trades GROUP BY account_name, symbol")
    rows = c.fetchall()
    end = time.time()
    print(f"Stats subquery took: {end-start:.4f}s ({len(rows)} groups)")

    print("\n--- Indices on processed_trades ---")
    c.execute("PRAGMA index_list(processed_trades)")
    for idx in c.fetchall():
        print(idx)
        c.execute(f"PRAGMA index_info({idx[1]})")
        print(f"  Columns: {c.fetchall()}")

    conn.close()

if __name__ == "__main__":
    profile_queries()
