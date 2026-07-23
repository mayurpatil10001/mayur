"""
scripts/inspect_10_sequences.py
===============================
Extracts 10 real fill sequences from Sierra Chart binary files
to illustrate clean fills vs. ghost fill position corruption.
"""

import os
import glob
import sqlite3
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "trading_platform.db"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Find top accounts with trades
    c.execute("""
        SELECT account_name, symbol, count(*), avg(quantity), max(quantity)
        FROM processed_trades
        GROUP BY account_name, symbol
        HAVING count(*) >= 1000
        ORDER BY count(*) DESC
        LIMIT 10
    """)
    accounts = c.fetchall()

    print("=" * 100)
    print(" TOP 10 ACCOUNT / SYMBOL SEQUENCES AUDIT")
    print("=" * 100)

    for idx, (acc, sym, count, avg_q, max_q) in enumerate(accounts, 1):
        # Fetch 5 sample trade sequences for this account
        c.execute("""
            SELECT entry_time, exit_time, side, entry_price, exit_price, quantity, profit_loss, duration_minutes
            FROM processed_trades
            WHERE account_name = ? AND symbol = ?
            ORDER BY entry_time ASC
            LIMIT 5
        """, (acc, sym))
        trades = c.fetchall()

        c.execute("""
            SELECT count(*), sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END)
            FROM processed_trades
            WHERE account_name = ? AND symbol = ?
        """, (acc, sym))
        tot, gt3 = c.fetchone()
        bad_pct = (gt3 / float(tot) * 100.0) if tot > 0 else 0.0

        print(f"\n--- SEQUENCE EXAMPLE #{idx}: Account '{acc}' | Symbol '{sym}' ---")
        print(f"Total Trades: {tot:,} | Bad Trades (Qty > 3): {gt3} ({bad_pct:.2f}%) | Max Qty: {max_q}")
        print(f"{'#':<3} | {'Entry Time (NY)':<20} | {'Exit Time (NY)':<20} | {'Side':<5} | {'Entry':<8} | {'Exit':<8} | {'Qty':<4} | {'PnL ($)':<10}")
        print("-" * 95)

        for t_idx, tr in enumerate(trades, 1):
            e_t, x_t, side, e_p, x_p, qty, pnl, dur = tr
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "$0.00"
            print(f"{t_idx:<3} | {e_t[:19]:<20} | {x_t[:19]:<20} | {side:<5} | {e_p:<8.2f} | {x_p:<8.2f} | {qty:<4} | {pnl_str:<10}")

    conn.close()

if __name__ == "__main__":
    main()
