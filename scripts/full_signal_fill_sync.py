"""
scripts/full_signal_fill_sync.py
=================================
Full sync of all GraphData bar signals (June 10 – July 23, 2026)
against actual NQ executions from IPS_TM_7 binary log files.

For each trading day:
- Extracts bar signals from GraphData txt (direction, time, price)
- Extracts clean NQ fills from IPS_TM_7 binary logs (ghost fills removed)
- Matches each signal bar to the nearest execution fill within ±5 minutes
- Computes daily Signal Count, Fill Count, Match Rate, Ghost Count
- Exports full day-by-day report to docs/tm7_nq_full_signal_fill_sync.csv
"""

import os, sys, csv, re, glob, struct, datetime
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GRAPHDATA_FILE = PROJECT_ROOT / "TM_7_NQU26 [CBV][M]  1000 Volume #5_GraphData (1).txt"
DATASET_DIR    = PROJECT_ROOT / "dataset"
OUTPUT_CSV     = PROJECT_ROOT / "docs" / "tm7_nq_full_signal_fill_sync.csv"
MATCH_WINDOW_MIN = 5  # minutes tolerance for signal-to-fill match

# ── Parse ALL bar signals from GraphData ─────────────────────────────────────
def parse_all_signals():
    signals = defaultdict(list)
    with open(str(GRAPHDATA_FILE), "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 32: continue
        try:
            raw_date = parts[0]
            time_str = parts[1][:8]
            buy_price  = float(parts[13])
            sell_price = float(parts[14])
        except: continue
        if buy_price == 0 and sell_price == 0: continue
        d_parts = raw_date.split("-")
        iso_date = f"{d_parts[0]}-{int(d_parts[1]):02d}-{int(d_parts[2]):02d}"
        signals[iso_date].append({
            "time": time_str,
            "direction": "BUY" if buy_price > 0 else "SELL",
            "price": buy_price if buy_price > 0 else sell_price,
        })
    return signals

# ── Parse NQ fills from IPS_TM_7 using production parser ────────────────────
def get_nq_fills_for_date(date_str):
    from trading_platform.services.binary_log_parser import _parse_file_nitro
    fp = DATASET_DIR / f"TradeActivityLog_{date_str}_UTC.IPS_TM_7.data"
    if not fp.exists():
        return [], 0
    raw_fills, _ = _parse_file_nitro(str(fp))
    nq_fills = [f for f in raw_fills if "NQ" in str(f.get("symbol", ""))]
    ghost_cnt = sum(1 for f in nq_fills if f.get("suggests_ghost"))
    clean_fills = [f for f in nq_fills if not f.get("suggests_ghost")]
    return clean_fills, ghost_cnt

# ── Match signals to fills ───────────────────────────────────────────────────
def match_signals_to_fills(signals, fills):
    matched = 0
    unmatched_signals = []
    for sig in signals:
        sig_h, sig_m, sig_s = [int(x) for x in sig["time"].split(":")]
        sig_total_min = sig_h * 60 + sig_m
        best_match = None
        best_diff  = MATCH_WINDOW_MIN + 1
        for fill in fills:
            ts = fill.get("timestamp", "")
            if not ts or len(ts) < 8: continue
            try:
                f_h, f_m = int(ts[11:13]), int(ts[14:16])
                f_total_min = f_h * 60 + f_m
                diff = abs(f_total_min - sig_total_min)
                if diff < best_diff:
                    best_diff = diff
                    best_match = fill
            except: continue
        if best_match and best_diff <= MATCH_WINDOW_MIN:
            matched += 1
        else:
            unmatched_signals.append(sig)
    return matched, unmatched_signals

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("FULL SIGNAL-TO-FILL SYNC: Jun 10 - Jul 23, 2026 | TM_7 / NQ")
    print("=" * 65)

    all_signals = parse_all_signals()
    active_dates = sorted(all_signals.keys())
    # Filter to GraphData window: Jun 10 – Jul 23, 2026
    active_dates = [d for d in active_dates if "2026-06-10" <= d <= "2026-07-23"]

    print(f"Total Signal Days in GraphData: {len(active_dates)}")
    print(f"Total Bar Signals: {sum(len(all_signals[d]) for d in active_dates)}\n")

    rows = []
    total_signals = total_fills = total_matched = total_ghosts = 0

    for date in active_dates:
        day_signals = all_signals[date]
        clean_fills, ghost_cnt = get_nq_fills_for_date(date)
        matched, unmatched = match_signals_to_fills(day_signals, clean_fills)
        match_rate = f"{matched/len(day_signals)*100:.1f}%" if day_signals else "N/A"

        print(f"{date} | Signals: {len(day_signals):3d} | NQ Clean Fills: {len(clean_fills):3d} | "
              f"Ghosts Dropped: {ghost_cnt:2d} | Matched: {matched:3d} | Match Rate: {match_rate}")

        total_signals += len(day_signals)
        total_fills   += len(clean_fills)
        total_matched += matched
        total_ghosts  += ghost_cnt

        rows.append({
            "date": date,
            "signals": len(day_signals),
            "clean_fills": len(clean_fills),
            "ghosts_dropped": ghost_cnt,
            "signals_matched": matched,
            "unmatched_signals": len(unmatched),
            "match_rate": match_rate,
        })

    print(f"\nTOTALS | Signals: {total_signals} | Clean NQ Fills: {total_fills} | "
          f"Ghosts Dropped: {total_ghosts} | Matched: {total_matched} | "
          f"Overall Match Rate: {total_matched/total_signals*100:.1f}%")

    # Write CSV
    os.makedirs(str(OUTPUT_CSV.parent), exist_ok=True)
    with open(str(OUTPUT_CSV), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["FULL SIGNAL-TO-FILL SYNC REPORT | TM_7 NQ | Jun 10 - Jul 23, 2026"])
        w.writerow(["Date", "Bar_Signals", "NQ_Clean_Fills", "Ghost_Fills_Dropped",
                    "Signals_Matched_to_Fill", "Unmatched_Signals", "Match_Rate_%"])
        for r in rows:
            w.writerow([r["date"], r["signals"], r["clean_fills"], r["ghosts_dropped"],
                        r["signals_matched"], r["unmatched_signals"], r["match_rate"]])
        w.writerow([])
        w.writerow(["TOTAL", total_signals, total_fills, total_ghosts, total_matched,
                    total_signals - total_matched,
                    f"{total_matched/total_signals*100:.1f}%" if total_signals else "N/A"])

    print(f"\nExported: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
