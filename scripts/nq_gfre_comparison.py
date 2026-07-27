"""
scripts/nq_gfre_comparison.py
==============================
Full NQ dirty-vs-clean comparison for June 10 - July 23, 2026.
Runs the Ghost Fill Resynchronization Engine on every active IPS_TM_7
NQ day and compares:
  - DIRTY  : all fills, no ghost removal (what the old DB had)
  - GFRE   : ghost fills purged, FIFO re-paired trades

Outputs: docs/nq_gfre_comparison_jun10_jul23.csv
"""
import sys, os, glob, csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine  import GhostFillEngine, FillRecord, pair_fills_to_trades

DATASET   = os.path.join(os.path.dirname(__file__), "..", "dataset")
OUTPUT    = os.path.join(os.path.dirname(__file__), "..", "docs", "nq_gfre_comparison_jun10_jul23.csv")
DATE_FROM = "2026-06-10"
DATE_TO   = "2026-07-23"

def _net(trades):
    return sum(t.pnl_dollars for t in trades)

def _wins(trades):
    return sum(1 for t in trades if t.pnl_dollars > 0)

def _max_dd(trades):
    """Peak-to-trough drawdown on cumulative PnL series."""
    if not trades: return 0.0
    cum, peak, dd = 0.0, 0.0, 0.0
    for t in trades:
        cum += t.pnl_dollars
        if cum > peak: peak = cum
        if (peak - cum) > dd: dd = peak - cum
    return dd

def run():
    files = sorted(
        glob.glob(os.path.join(DATASET, "TradeActivityLog_2026-06-*.IPS_TM_7.data")) +
        glob.glob(os.path.join(DATASET, "TradeActivityLog_2026-07-*.IPS_TM_7.data"))
    )
    files = [f for f in files
             if DATE_FROM <= os.path.basename(f).split("_")[1] <= DATE_TO]

    engine = GhostFillEngine()
    rows   = []
    all_dirty_trades  = []
    all_clean_trades  = []

    print(f"{'Date':<12} | {'D-Raw':>6} | {'D-Trades':>8} | {'D-Net':>10} | "
          f"{'G-Ghost':>7} | {'G-Trades':>8} | {'G-Net':>10} | {'Delta$':>10} | {'Flips':>5}")
    print("-" * 95)

    for fp in files:
        date = os.path.basename(fp).split("_")[1]
        raw, _ = _parse_file_nitro(fp)
        nq_raw = [f for f in raw if "NQ" in str(f.get("symbol", ""))]
        if not nq_raw:
            continue

        # -- DIRTY (no ghost filter, all fills into FIFO) ------------------
        dirty_fills = GhostFillEngine.from_dicts(nq_raw)
        # Force all as non-ghost for dirty run
        for f in dirty_fills: f.suggests_ghost = False
        dirty_trades, _ = pair_fills_to_trades(dirty_fills)

        # -- CLEAN (GFRE applied) ------------------------------------------
        gfre_fills  = GhostFillEngine.from_dicts(nq_raw)
        result      = engine.process(gfre_fills)
        clean_trades = result.trades

        # Accumulate for totals
        all_dirty_trades.extend(dirty_trades)
        all_clean_trades.extend(clean_trades)

        d_net   = _net(dirty_trades)
        g_net   = _net(clean_trades)
        delta   = g_net - d_net
        ghosts  = result.ghost_fills_dropped
        flips   = result.direction_flips

        print(f"{date:<12} | {len(nq_raw):>6} | {len(dirty_trades):>8} | "
              f"${d_net:>9,.0f} | {ghosts:>7} | {len(clean_trades):>8} | "
              f"${g_net:>9,.0f} | ${delta:>+9,.0f} | {flips:>5}")

        rows.append({
            "date": date,
            "dirty_raw_fills":   len(nq_raw),
            "dirty_trades":      len(dirty_trades),
            "dirty_wins":        _wins(dirty_trades),
            "dirty_losses":      len(dirty_trades) - _wins(dirty_trades),
            "dirty_net_pnl":     round(d_net, 2),
            "dirty_win_rate":    f"{_wins(dirty_trades)/len(dirty_trades)*100:.1f}%" if dirty_trades else "N/A",
            "dirty_max_dd":      round(_max_dd(dirty_trades), 2),
            "gfre_ghosts_dropped":  ghosts,
            "gfre_clean_fills":     result.clean_fills,
            "gfre_trades":          len(clean_trades),
            "gfre_wins":            _wins(clean_trades),
            "gfre_losses":          len(clean_trades) - _wins(clean_trades),
            "gfre_net_pnl":         round(g_net, 2),
            "gfre_win_rate":        f"{_wins(clean_trades)/len(clean_trades)*100:.1f}%" if clean_trades else "N/A",
            "gfre_max_dd":          round(_max_dd(clean_trades), 2),
            "pnl_delta":            round(delta, 2),
            "direction_flips_clean": flips,
            "integrity_ok":         result.integrity_ok,
        })

    # -- Totals ------------------------------------------------------------
    print("-" * 95)
    td = _net(all_dirty_trades); tg = _net(all_clean_trades)
    print(f"{'TOTAL':<12} | {'':>6} | {len(all_dirty_trades):>8} | "
          f"${td:>9,.0f} | {'':>7} | {len(all_clean_trades):>8} | "
          f"${tg:>9,.0f} | ${tg-td:>+9,.0f} |")

    # -- Write CSV ---------------------------------------------------------
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["NQ GFRE COMPARISON REPORT | IPS_TM_7 | Jun 10 - Jul 23, 2026"])
        w.writerow([
            "Date",
            "Dirty_Raw_Fills", "Dirty_Trades", "Dirty_Wins", "Dirty_Losses",
            "Dirty_Net_PnL", "Dirty_Win_Rate%", "Dirty_MaxDD",
            "GFRE_Ghosts_Dropped", "GFRE_Clean_Fills",
            "GFRE_Trades", "GFRE_Wins", "GFRE_Losses",
            "GFRE_Net_PnL", "GFRE_Win_Rate%", "GFRE_MaxDD",
            "PnL_Delta", "Direction_Flips_Clean", "Integrity_OK"
        ])
        for r in rows:
            w.writerow([
                r["date"],
                r["dirty_raw_fills"], r["dirty_trades"], r["dirty_wins"], r["dirty_losses"],
                r["dirty_net_pnl"], r["dirty_win_rate"], r["dirty_max_dd"],
                r["gfre_ghosts_dropped"], r["gfre_clean_fills"],
                r["gfre_trades"], r["gfre_wins"], r["gfre_losses"],
                r["gfre_net_pnl"], r["gfre_win_rate"], r["gfre_max_dd"],
                r["pnl_delta"], r["direction_flips_clean"], r["integrity_ok"]
            ])
        # Totals row
        w.writerow([])
        w.writerow([
            "TOTAL",
            "", len(all_dirty_trades), _wins(all_dirty_trades),
            len(all_dirty_trades)-_wins(all_dirty_trades),
            round(td, 2),
            f"{_wins(all_dirty_trades)/len(all_dirty_trades)*100:.1f}%" if all_dirty_trades else "N/A",
            round(_max_dd(all_dirty_trades), 2),
            "", "",
            len(all_clean_trades), _wins(all_clean_trades),
            len(all_clean_trades)-_wins(all_clean_trades),
            round(tg, 2),
            f"{_wins(all_clean_trades)/len(all_clean_trades)*100:.1f}%" if all_clean_trades else "N/A",
            round(_max_dd(all_clean_trades), 2),
            round(tg - td, 2), "", ""
        ])
    print(f"\nExported: {OUTPUT}")

if __name__ == "__main__":
    run()
