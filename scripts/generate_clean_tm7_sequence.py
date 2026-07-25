"""
scripts/generate_clean_tm7_sequence.py
======================================
Builds the exact, clean, resynchronized Strategy-Based Trade Sequence for TM_7 NQ:
1. Removes all Ghost Fills (un-tagged executions).
2. Pairs clean entry/exit strategy fills into completed trades (FIFO / Sierra Chart execution order).
3. Generates the exact strategy trade list:
   - Trade #, Date, Entry Time, Exit Time, Direction, Qty, Entry Price, Exit Price, PnL ($), Cumulative PnL ($), Holding Duration (mins)
4. Appends Section E to docs/tm7_nq_ghost_analysis.csv and saves docs/tm7_nq_clean_strategy_trades.csv.
"""

import os
import sys
import csv
import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.tm7_nq_ghost_analysis import extract_position_fills, parse_signals

NQ_MULTIPLIER = 20  # $20 per point for NQ
NQ_TICK_SIZE = 0.25

DATASET_DIR = PROJECT_ROOT / "dataset"
OUTPUT_ANALYSIS_CSV = PROJECT_ROOT / "docs" / "tm7_nq_ghost_analysis.csv"
OUTPUT_CLEAN_CSV = PROJECT_ROOT / "docs" / "tm7_nq_clean_strategy_trades.csv"

DATES = ["2026-06-10", "2026-06-11", "2026-06-12"]

def build_clean_trades(date_str):
    fpath = DATASET_DIR / f"TradeActivityLog_{date_str}_UTC.TM_7.data"
    if not fpath.exists():
        return []

    # Extract position fills
    raw_fills = extract_position_fills(str(fpath), date_str)
    # Filter NQ price range + clean fills ONLY (drop ghosts)
    clean_fills = [
        f for f in raw_fills
        if 15000 <= f.get("fill_price", 0) <= 35000 and not f.get("is_ghost")
    ]

    # Pair clean fills into FIFO completed trades
    trades = []
    open_positions = []  # [{side, qty, price, time}]

    trade_num = 1
    for f in clean_fills:
        fill_side = f["side"]
        fill_qty = f["qty_delta"]
        fill_price = f["fill_price"]
        fill_time = f["fill_time"]

        # Match against opposite side in open_positions
        rem_qty = fill_qty
        while rem_qty > 0 and open_positions:
            pos = open_positions[0]
            if pos["side"] != fill_side:
                matched_qty = min(rem_qty, pos["qty"])

                # Calculate PnL
                if pos["side"] == "BUY":  # Long trade
                    pnl_pts = fill_price - pos["price"]
                else:  # Short trade
                    pnl_pts = pos["price"] - fill_price

                pnl_dollars = pnl_pts * NQ_MULTIPLIER * matched_qty

                # Duration
                try:
                    t1 = datetime.datetime.strptime(pos["time"], "%H:%M:%S")
                    t2 = datetime.datetime.strptime(fill_time, "%H:%M:%S")
                    dur_min = round((t2 - t1).total_seconds() / 60.0, 1)
                    if dur_min < 0:
                        dur_min += 1440.0
                except:
                    dur_min = 0.0

                trades.append({
                    "date": date_str,
                    "trade_num": trade_num,
                    "direction": pos["side"],
                    "qty": matched_qty,
                    "entry_time": pos["time"],
                    "exit_time": fill_time,
                    "entry_price": pos["price"],
                    "exit_price": fill_price,
                    "pnl_points": round(pnl_pts, 2),
                    "pnl_dollars": round(pnl_dollars, 2),
                    "duration_min": dur_min,
                })
                trade_num += 1

                rem_qty -= matched_qty
                pos["qty"] -= matched_qty
                if pos["qty"] <= 0:
                    open_positions.pop(0)
            else:
                break

        # Remaining qty opens new position
        if rem_qty > 0:
            open_positions.append({
                "side": fill_side,
                "qty": rem_qty,
                "price": fill_price,
                "time": fill_time,
            })

    return trades


def main():
    print("=" * 60)
    print("Generating Clean Strategy-Based Trade Sequence for TM_7 NQ")
    print("=" * 60)

    all_clean_trades = []
    cum_pnl = 0.0

    for d in DATES:
        day_trades = build_clean_trades(d)
        print(f"\nDate: {d} | Clean Strategy Trades Matched: {len(day_trades)}")
        for t in day_trades:
            cum_pnl += t["pnl_dollars"]
            t["cum_pnl"] = round(cum_pnl, 2)
            all_clean_trades.append(t)
            print(f"  Trade #{t['trade_num']:02d} | {t['direction']:5s} {t['qty']}x | "
                  f"Entry {t['entry_time']} @ {t['entry_price']} -> Exit {t['exit_time']} @ {t['exit_price']} | "
                  f"PnL: ${t['pnl_dollars']:+,.2f} | Cum: ${t['cum_pnl']:+,.2f}")

    # Write separate CSV for clean strategy trades
    with open(str(OUTPUT_CLEAN_CSV), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["SECTION: CLEAN STRATEGY-BASED TRADES (Ghost Fills Removed)"])
        writer.writerow(["Date", "Trade_#", "Direction", "Qty", "Entry_Time", "Exit_Time",
                         "Entry_Price", "Exit_Price", "PnL_Points", "PnL_Dollars", "Cum_PnL_Dollars", "Duration_Min"])
        for t in all_clean_trades:
            writer.writerow([
                t["date"], t["trade_num"], t["direction"], t["qty"],
                t["entry_time"], t["exit_time"], t["entry_price"], t["exit_price"],
                t["pnl_points"], t["pnl_dollars"], t["cum_pnl"], t["duration_min"]
            ])

    print(f"\nSaved Clean Strategy Trades to: {OUTPUT_CLEAN_CSV}")

    # Append to tm7_nq_ghost_analysis.csv as Section E
    with open(str(OUTPUT_ANALYSIS_CSV), "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([])
        writer.writerow(["SECTION E: CLEAN STRATEGY-BASED TRADE SEQUENCE (RESYNCHRONIZED - GHOSTS REMOVED)"])
        writer.writerow(["Date", "Trade_#", "Direction", "Qty", "Entry_Time", "Exit_Time",
                         "Entry_Price", "Exit_Price", "PnL_Points", "PnL_Dollars", "Cum_PnL_Dollars", "Duration_Min"])
        for t in all_clean_trades:
            writer.writerow([
                t["date"], t["trade_num"], t["direction"], t["qty"],
                t["entry_time"], t["exit_time"], t["entry_price"], t["exit_price"],
                t["pnl_points"], t["pnl_dollars"], t["cum_pnl"], t["duration_min"]
            ])

    print(f"Appended Section E to: {OUTPUT_ANALYSIS_CSV}")


if __name__ == "__main__":
    main()
