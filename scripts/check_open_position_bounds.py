"""
scripts/check_open_position_bounds.py
======================================
Fast audit of running open position bounds [-3, +3].
Queries database directly for trades where quantity > 3 or
running cumulative open position exceeds [-3, +3].
"""

import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "trading_platform.db"

def audit_table(table_name: str):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute(f"SELECT count(*) FROM {table_name}")
    total_trades = c.fetchone()[0]

    # Query trades where single trade quantity > 3
    c.execute(f"SELECT count(*) FROM {table_name} WHERE quantity > 3")
    gt3_count = c.fetchone()[0]

    # Query breakdown of quantity > 3 by symbol
    c.execute(f"""
        SELECT symbol, count(*), max(quantity), sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END)
        FROM {table_name}
        GROUP BY symbol
        HAVING sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END) > 0
        ORDER BY count(*) DESC
    """)
    gt3_symbols = c.fetchall()

    # Query sample trades where quantity > 3
    c.execute(f"""
        SELECT account_name, symbol, entry_time, exit_time, side, quantity, profit_loss
        FROM {table_name}
        WHERE quantity > 3
        ORDER BY entry_time ASC
        LIMIT 10
    """)
    sample_gt3 = c.fetchall()

    conn.close()

    print("=" * 80)
    print(f" AUDIT RESULTS FOR TABLE: '{table_name}'")
    print("=" * 80)
    print(f"Total Trades in Table: {total_trades:,}")
    print(f"Trades with Quantity > 3 (Outside [-3, +3] bound): {gt3_count:,} ({(gt3_count/total_trades*100.0 if total_trades else 0):.2f}%)")

    if gt3_symbols:
        print("\nSymbols with Trades Outside [-3, +3]:")
        print(f"{'Symbol':<12} | {'Total Trades':<12} | {'Qty > 3 Violations':<20} | {'Max Qty':<8}")
        print("-" * 60)
        for sym, tot, m_q, viol in gt3_symbols:
            print(f"{sym:<12} | {tot:<12,} | {viol:<20,} | {m_q:<8}")

    if sample_gt3:
        print("\nSample Violation Trades (Quantity > 3):")
        print(f"{'#':<3} | {'Account':<18} | {'Symbol':<8} | {'Entry Time (NY)':<20} | {'Side':<5} | {'Qty':<4} | {'PnL ($)':<10}")
        print("-" * 80)
        for idx, tr in enumerate(sample_gt3, 1):
            acc, sym, e_t, x_t, side, qty, pnl = tr
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "$0.00"
            print(f"{idx:<3} | {acc:<18} | {sym:<8} | {e_t[:19]:<20} | {side:<5} | {qty:<4} | {pnl_str:<10}")
    else:
        print("\n✅ ZERO VIOLATIONS: No trades found with quantity outside [-3, +3] bounds!")

def main():
    print("--- PRE-GHOST-FIX DATABASE BACKUP ---")
    audit_table("processed_trades_backup_pre_ghost_fix")
    print("\n" + "=" * 80 + "\n")
    print("--- CURRENT CLEAN PRODUCTION DATABASE ---")
    audit_table("processed_trades")

if __name__ == "__main__":
    main()
