"""
scripts/export_problematic_sequences.py
=======================================
Exports all problematic trade sequences (Quantity > 3) from both
processed_trades (Clean DB) and processed_trades_backup_pre_ghost_fix (Pre-Fix DB)
into CSV and TXT files for user review.

Outputs:
- docs/problematic_trade_sequences.csv (Openable directly in Microsoft Excel)
- docs/problematic_trade_sequences.txt (Clean formatted text file)
"""

import sqlite3
import csv
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "trading_platform.db"
CSV_OUT = PROJECT_ROOT / "docs" / "problematic_trade_sequences.csv"
TXT_OUT = PROJECT_ROOT / "docs" / "problematic_trade_sequences.txt"

def main():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Query 1: Clean DB problematic trades (Qty > 3)
    c.execute("""
        SELECT 
            'Clean_DB (processed_trades)' as db_source,
            account_name, symbol, trade_id, entry_time, exit_time, side,
            entry_price, exit_price, quantity, profit_loss, duration_minutes,
            hour_of_day, day_of_week
        FROM processed_trades
        WHERE quantity > 3
        ORDER BY symbol, account_name, entry_time ASC
    """)
    clean_bad_trades = c.fetchall()

    # Query 2: Pre-Fix DB problematic trades (Qty > 3)
    c.execute("""
        SELECT 
            'Pre_Fix_DB (processed_trades_backup_pre_ghost_fix)' as db_source,
            account_name, symbol, trade_id, entry_time, exit_time, side,
            entry_price, exit_price, quantity, profit_loss, duration_minutes,
            hour_of_day, day_of_week
        FROM processed_trades_backup_pre_ghost_fix
        WHERE quantity > 3
        ORDER BY symbol, account_name, entry_time ASC
    """)
    prefix_bad_trades = c.fetchall()

    conn.close()

    os.makedirs(CSV_OUT.parent, exist_ok=True)

    # 1. Export CSV (Excel Compatible)
    headers = [
        "Database_Source", "Account_Name", "Symbol", "Trade_ID",
        "Entry_Time_NY", "Exit_Time_NY", "Side", "Entry_Price",
        "Exit_Price", "Quantity", "Profit_Loss_USD", "Duration_Minutes",
        "Hour_of_Day_NY", "Day_of_Week"
    ]

    all_records = clean_bad_trades + prefix_bad_trades

    with open(str(CSV_OUT), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in all_records:
            writer.writerow(row)

    print(f"Exported {len(all_records):,} total problematic trade records to CSV:")
    print(f"  -> {CSV_OUT}")
    print(f"     - Clean DB (processed_trades): {len(clean_bad_trades):,} records")
    print(f"     - Pre-Fix DB (processed_trades_backup_pre_ghost_fix): {len(prefix_bad_trades):,} records")

    # 2. Export TXT (Formatted Text Report)
    with open(str(TXT_OUT), "w", encoding="utf-8") as f:
        f.write("=" * 110 + "\n")
        f.write(" SIERRA CHART TRADE OPTIMIZATION PLATFORM — PROBLEMATIC TRADE SEQUENCES AUDIT\n")
        f.write(" Criteria: Trades with Quantity > 3 Contracts (Exceeding [-3, +3] Position Limit)\n")
        f.write("=" * 110 + "\n\n")

        f.write(f"PART 1: CURRENT CLEAN PRODUCTION DATABASE (processed_trades)\n")
        f.write(f"Total Problematic Trades Found: {len(clean_bad_trades):,}\n")
        f.write("-" * 110 + "\n")
        f.write(f"{'#':<4} | {'Account':<18} | {'Symbol':<10} | {'Entry Time (NY)':<19} | {'Side':<5} | {'Entry':<9} | {'Exit':<9} | {'Qty':<4} | {'PnL ($)':<10}\n")
        f.write("-" * 110 + "\n")

        for idx, row in enumerate(clean_bad_trades, 1):
            _, acc, sym, tid, e_t, x_t, side, e_p, x_p, qty, pnl, dur, h, dow = row
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "$0.00"
            f.write(f"{idx:<4} | {acc:<18} | {sym:<10} | {e_t[:19]:<19} | {side:<5} | {e_p:<9.2f} | {x_p:<9.2f} | {qty:<4} | {pnl_str:<10}\n")

        f.write("\n\n" + "=" * 110 + "\n")
        f.write(f"PART 2: PRE-FIX HISTORICAL DATABASE BACKUP (processed_trades_backup_pre_ghost_fix)\n")
        f.write(f"Total Problematic Trades Found: {len(prefix_bad_trades):,}\n")
        f.write("-" * 110 + "\n")
        f.write(f"{'#':<4} | {'Account':<18} | {'Symbol':<10} | {'Entry Time (NY)':<19} | {'Side':<5} | {'Entry':<9} | {'Exit':<9} | {'Qty':<4} | {'PnL ($)':<10}\n")
        f.write("-" * 110 + "\n")

        for idx, row in enumerate(prefix_bad_trades, 1):
            _, acc, sym, tid, e_t, x_t, side, e_p, x_p, qty, pnl, dur, h, dow = row
            pnl_str = f"${pnl:,.2f}" if pnl is not None else "$0.00"
            f.write(f"{idx:<4} | {acc:<18} | {sym:<10} | {e_t[:19]:<19} | {side:<5} | {e_p:<9.2f} | {x_p:<9.2f} | {qty:<4} | {pnl_str:<10}\n")

    print(f"Exported formatted text report to TXT:")
    print(f"  -> {TXT_OUT}")

if __name__ == "__main__":
    main()
