"""
scripts/analyze_qty_breakdown.py
================================
Contract-by-contract audit of trade quantities.
Identifies problematic trades where quantity > 3.
"""

import sqlite3
import os

DB_PATH = "trading_platform.db"

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT count(*) FROM processed_trades")
    total_trades = c.fetchone()[0]

    c.execute("""
        SELECT 
            symbol, 
            count(*) as total, 
            sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END) as gt3,
            sum(CASE WHEN quantity = 1 THEN 1 ELSE 0 END) as q1,
            sum(CASE WHEN quantity BETWEEN 2 AND 3 THEN 1 ELSE 0 END) as q23,
            avg(quantity) as avg_q, 
            max(quantity) as max_q
        FROM processed_trades 
        GROUP BY symbol 
        ORDER BY total DESC
    """)
    rows = c.fetchall()

    print("=" * 90)
    print(f" TOTAL TRADES IN DATABASE: {total_trades:,}")
    print("=" * 90)
    print(f"{'Symbol':<10} | {'Total Trades':<12} | {'Qty > 3 (Bad)':<15} | {'% Bad':<10} | {'Qty 1':<10} | {'Qty 2-3':<10} | {'Max Qty':<8}")
    print("-" * 90)

    for sym, total, gt3, q1, q23, avg_q, max_q in rows:
        pct = (gt3 / total * 100.0) if total > 0 else 0.0
        print(f"{sym:<10} | {total:<12,} | {gt3:<15,} | {pct:<9.2f}% | {q1:<10,} | {q23:<10,} | {max_q:<8}")

    print("-" * 90)

    # Check across all tables in DB if any un-filtered tables exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    print("\nAll DB Tables:", tables)

    for tbl in tables:
        try:
            c.execute(f"SELECT count(*), sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END) FROM {tbl}")
            cnt, gt3_cnt = c.fetchone()
            print(f"Table '{tbl}': {cnt:,} total rows | {gt3_cnt:,} rows with quantity > 3")
        except Exception as e:
            pass

    conn.close()

if __name__ == "__main__":
    main()
