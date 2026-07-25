"""
scripts/inspect_problematic_sequences.py
========================================
Extracts raw binary fill sequences where ghost fills occur.
Compares occurrence across NQ, ES, FDAX, and CL.
Answers whether DAX (FDAX) has ghost fills or not.
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

    # Query quantity > 3 violations per asset class (NQ vs ES vs FDAX vs CL)
    c.execute("""
        SELECT 
            CASE 
                WHEN symbol LIKE 'NQ%' OR symbol LIKE 'MNQ%' THEN 'NQ (Nasdaq)'
                WHEN symbol LIKE 'ES%' OR symbol LIKE 'MES%' THEN 'ES (S&P 500)'
                WHEN symbol LIKE 'FDAX%' THEN 'FDAX (DAX Futures)'
                WHEN symbol LIKE 'CL%' OR symbol LIKE 'MCL%' THEN 'CL (Crude Oil)'
                WHEN symbol LIKE 'Z%' THEN 'Bonds (ZB/ZN)'
                ELSE 'Other'
            END as asset_class,
            count(*) as total_trades,
            sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END) as bad_trades,
            sum(CASE WHEN quantity = 1 THEN 1 ELSE 0 END) as qty_1,
            sum(CASE WHEN quantity BETWEEN 2 AND 3 THEN 1 ELSE 0 END) as qty_2_3,
            max(quantity) as max_qty
        FROM processed_trades
        GROUP BY asset_class
        ORDER BY total_trades DESC
    """)
    asset_breakdown = c.fetchall()

    # Query pre-fix database breakdown by asset class
    c.execute("""
        SELECT 
            CASE 
                WHEN symbol LIKE 'NQ%' OR symbol LIKE 'MNQ%' THEN 'NQ (Nasdaq)'
                WHEN symbol LIKE 'ES%' OR symbol LIKE 'MES%' THEN 'ES (S&P 500)'
                WHEN symbol LIKE 'FDAX%' THEN 'FDAX (DAX Futures)'
                WHEN symbol LIKE 'CL%' OR symbol LIKE 'MCL%' THEN 'CL (Crude Oil)'
                WHEN symbol LIKE 'Z%' THEN 'Bonds (ZB/ZN)'
                ELSE 'Other'
            END as asset_class,
            count(*) as total_trades,
            sum(CASE WHEN quantity > 3 THEN 1 ELSE 0 END) as bad_trades,
            max(quantity) as max_qty
        FROM processed_trades_backup_pre_ghost_fix
        GROUP BY asset_class
        ORDER BY total_trades DESC
    """)
    prefix_asset_breakdown = c.fetchall()

    # Get sample FDAX problematic trade sequences
    c.execute("""
        SELECT account_name, symbol, entry_time, exit_time, side, quantity, profit_loss
        FROM processed_trades
        WHERE symbol LIKE 'FDAX%' AND quantity > 3
        ORDER BY entry_time ASC
        LIMIT 10
    """)
    fdax_bad_trades = c.fetchall()

    # Get sample NQ, ES, CL problematic trade sequences
    c.execute("""
        SELECT account_name, symbol, entry_time, exit_time, side, quantity, profit_loss
        FROM processed_trades
        WHERE quantity > 3
        ORDER BY entry_time ASC
        LIMIT 10
    """)
    sample_bad_trades = c.fetchall()

    conn.close()

    print("=" * 90)
    print(" 1. ASSET CLASS BREAKDOWN: CURRENT CLEAN DATABASE (processed_trades)")
    print("=" * 90)
    print(f"{'Asset Class':<20} | {'Total Trades':<12} | {'Qty > 3 (Bad)':<15} | {'% Bad':<10} | {'Max Qty':<8}")
    print("-" * 75)
    for ac, tot, bad, q1, q23, max_q in asset_breakdown:
        pct = (bad / float(tot) * 100.0) if tot > 0 else 0.0
        print(f"{ac:<20} | {tot:<12,} | {bad:<15,} | {pct:<9.2f}% | {max_q:<8}")

    print("\n" + "=" * 90)
    print(" 2. ASSET CLASS BREAKDOWN: PRE-FIX DATABASE (processed_trades_backup_pre_ghost_fix)")
    print("=" * 90)
    print(f"{'Asset Class':<20} | {'Total Trades':<12} | {'Qty > 3 (Bad)':<15} | {'% Bad':<10} | {'Max Qty':<8}")
    print("-" * 75)
    for ac, tot, bad, max_q in prefix_asset_breakdown:
        pct = (bad / float(tot) * 100.0) if tot > 0 else 0.0
        print(f"{ac:<20} | {tot:<12,} | {bad:<15,} | {pct:<9.2f}% | {max_q:<8}")

    print("\n" + "=" * 90)
    print(" 3. FDAX (DAX FUTURES) SPECIFIC GHOST / OVER-SIZE SEQUENCE EXAMPLES")
    print("=" * 90)
    if fdax_bad_trades:
        print(f"{'#':<3} | {'Account':<15} | {'Symbol':<10} | {'Entry Time (NY)':<20} | {'Side':<5} | {'Qty':<4} | {'PnL ($)':<10}")
        print("-" * 80)
        for idx, tr in enumerate(fdax_bad_trades, 1):
            acc, sym, e_t, x_t, side, qty, pnl = tr
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "$0.00"
            print(f"{idx:<3} | {acc:<15} | {sym:<10} | {e_t[:19]:<20} | {side:<5} | {qty:<4} | {pnl_str:<10}")
    else:
        print("No FDAX trades found with Qty > 3 in current clean DB.")

if __name__ == "__main__":
    main()
