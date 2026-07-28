"""
Phase 3 — Re-run the exact 22-day NQ comparison using the FIXED, unified classifier.
Same scope as nq_gfre_comparison.py: IPS_TM_7, NQ, 2026-06-10 to 2026-07-23.
Reports new results side-by-side with the original broken run.
"""
import sys, os, glob, csv, datetime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, pair_fills_to_trades
)

# ── Original (broken) numbers from nq_gfre_comparison_jun10_jul23.csv ──────
# These are from the previous run — used only for side-by-side comparison.
ORIGINAL = {
    "2026-06-23": {"dirty_net": 3810,  "clean_net": -6810,  "dirty_wr": 78.6, "clean_wr": 48.7, "ghosts": 1},
    "2026-06-24": {"dirty_net": -3255, "clean_net": -3255,  "dirty_wr": 57.1, "clean_wr": 57.1, "ghosts": 0},
    "2026-06-25": {"dirty_net": -2440, "clean_net": 3595,   "dirty_wr": 66.7, "clean_wr": 54.0, "ghosts": 3},
    "2026-06-26": {"dirty_net": 13100, "clean_net": 3365,   "dirty_wr": 76.9, "clean_wr": 57.6, "ghosts": 2},
    "2026-06-28": {"dirty_net": -3570, "clean_net": -3570,  "dirty_wr": 0.0,  "clean_wr": 0.0,  "ghosts": 0},
    "2026-06-29": {"dirty_net": -1950, "clean_net": 31150,  "dirty_wr": 61.2, "clean_wr": 66.0, "ghosts": 2},
    "2026-06-30": {"dirty_net": 6955,  "clean_net": 6955,   "dirty_wr": 76.9, "clean_wr": 76.9, "ghosts": 0},
    "2026-07-01": {"dirty_net": 4795,  "clean_net": 7435,   "dirty_wr": 73.9, "clean_wr": 61.4, "ghosts": 1},
    "2026-07-02": {"dirty_net": -4960, "clean_net": -40795, "dirty_wr": 67.7, "clean_wr": 46.0, "ghosts": 1},
    "2026-07-03": {"dirty_net": -2800, "clean_net": -2800,  "dirty_wr": 40.0, "clean_wr": 40.0, "ghosts": 0},
    "2026-07-05": {"dirty_net": 1220,  "clean_net": 0,      "dirty_wr": 50.0, "clean_wr": 0.0,  "ghosts": 3},
    "2026-07-06": {"dirty_net": 10760, "clean_net": 10760,  "dirty_wr": 64.7, "clean_wr": 64.7, "ghosts": 0},
    "2026-07-07": {"dirty_net": -8560, "clean_net": -5930,  "dirty_wr": 53.8, "clean_wr": 52.9, "ghosts": 1},
    "2026-07-08": {"dirty_net": 4240,  "clean_net": 13425,  "dirty_wr": 74.6, "clean_wr": 78.2, "ghosts": 3},
    "2026-07-09": {"dirty_net": -5655, "clean_net": -22535, "dirty_wr": 55.2, "clean_wr": 36.0, "ghosts": 3},
    "2026-07-10": {"dirty_net": 4275,  "clean_net": 9585,   "dirty_wr": 76.2, "clean_wr": 68.4, "ghosts": 1},
    "2026-07-12": {"dirty_net": 5,     "clean_net": 5,      "dirty_wr": 66.7, "clean_wr": 66.7, "ghosts": 0},
    "2026-07-13": {"dirty_net": -1145, "clean_net": -16350, "dirty_wr": 66.7, "clean_wr": 38.5, "ghosts": 3},
    "2026-07-14": {"dirty_net": 3010,  "clean_net": 3200,   "dirty_wr": 71.8, "clean_wr": 75.0, "ghosts": 3},
    "2026-07-15": {"dirty_net": -8110, "clean_net": -820,   "dirty_wr": 56.2, "clean_wr": 45.7, "ghosts": 4},
    "2026-07-16": {"dirty_net": 10265, "clean_net": 10265,  "dirty_wr": 81.6, "clean_wr": 81.6, "ghosts": 0},
    "2026-07-17": {"dirty_net": -1190, "clean_net": -800,   "dirty_wr": 65.2, "clean_wr": 66.7, "ghosts": 2},
}

START = datetime.date(2026, 6, 10)
END   = datetime.date(2026, 7, 23)

results = []
totals = {"d_trades":0,"d_wins":0,"d_net":0,"c_trades":0,"c_wins":0,"c_net":0,"ghosts":0}
print(f"\n{'DATE':>10} | {'D-Tr':>5} | {'D-Net':>9} | {'D-Win%':>6} | {'Ghosts':>6} | {'C-Tr':>5} | {'C-Net':>9} | {'C-Win%':>6} | {'DELTA':>10} | OLD-DELTA vs NEW")
print("-"*110)

d = START
while d <= END:
    ds = d.strftime("%Y-%m-%d")
    fp = f"dataset/TradeActivityLog_{ds}_UTC.IPS_TM_7.data"
    d += datetime.timedelta(days=1)
    if not os.path.exists(fp):
        continue

    raw, _ = _parse_file_nitro(fp)
    nq = [f for f in raw if "NQ" in str(f.get("symbol", ""))]
    if not nq:
        continue

    fills = GhostFillEngine.from_dicts(nq)

    # Dirty run — no ghost filter
    dirty_all = [f for f in fills]
    for f in dirty_all:
        f.suggests_ghost = False
    dirty_trades, _ = pair_fills_to_trades(dirty_all)
    d_net   = sum(t.pnl_dollars for t in dirty_trades)
    d_wins  = sum(1 for t in dirty_trades if t.pnl_dollars > 0)
    d_wr    = 100 * d_wins / len(dirty_trades) if dirty_trades else 0

    # Clean run — fixed GFRE v2
    clean_fills_v2 = GhostFillEngine.from_dicts(nq)
    ghosts_v2  = [f for f in clean_fills_v2 if classify_fill(f)]
    clean_v2   = [f for f in clean_fills_v2 if not classify_fill(f)]
    c_trades, _ = pair_fills_to_trades(clean_v2)
    c_net   = sum(t.pnl_dollars for t in c_trades)
    c_wins  = sum(1 for t in c_trades if t.pnl_dollars > 0)
    c_wr    = 100 * c_wins / len(c_trades) if c_trades else 0
    n_ghosts = len(ghosts_v2)

    delta_new = c_net - d_net

    # Compare with old broken result for this date
    old = ORIGINAL.get(ds)
    if old:
        old_delta = old["clean_net"] - old["dirty_net"]
        comparison = f"old_delta=${old_delta:+,.0f} -> NEW=${delta_new:+,.0f}"
        fixed = " [FIXED]" if abs(delta_new) < abs(old_delta) else ""
    else:
        comparison = "(no prior result)"
        fixed = ""

    print(f"{ds:>10} | {len(dirty_trades):>5} | {d_net:>+9,.0f} | {d_wr:>5.1f}% | {n_ghosts:>6} | {len(c_trades):>5} | {c_net:>+9,.0f} | {c_wr:>5.1f}% | {delta_new:>+10,.0f} | {comparison}{fixed}")

    results.append({
        "date": ds,
        "dirty_trades": len(dirty_trades), "dirty_net": d_net, "dirty_wr": round(d_wr, 1),
        "ghosts_v2": n_ghosts,
        "clean_trades": len(c_trades), "clean_net": c_net, "clean_wr": round(c_wr, 1),
        "delta": delta_new,
    })
    totals["d_trades"] += len(dirty_trades)
    totals["d_wins"]   += d_wins
    totals["d_net"]    += d_net
    totals["c_trades"] += len(c_trades)
    totals["c_wins"]   += c_wins
    totals["c_net"]    += c_net
    totals["ghosts"]   += n_ghosts

print("-"*110)
d_wr_tot = 100 * totals["d_wins"] / totals["d_trades"] if totals["d_trades"] else 0
c_wr_tot = 100 * totals["c_wins"] / totals["c_trades"] if totals["c_trades"] else 0
print(f"{'TOTAL':>10} | {totals['d_trades']:>5} | {totals['d_net']:>+9,.0f} | {d_wr_tot:>5.1f}% | {totals['ghosts']:>6} | {totals['c_trades']:>5} | {totals['c_net']:>+9,.0f} | {c_wr_tot:>5.1f}% | {totals['c_net']-totals['d_net']:>+10,.0f}")

print(f"\n{'='*80}")
print(f"PHASE 3 COMPARISON: Original (v1 broken) vs Fixed (v2)")
print(f"{'='*80}")
print(f"  Original (v1): Dirty Net = +$18,800 | GFRE Clean Net = -$3,925 | DELTA = -$22,725")
print(f"  Fixed   (v2): Dirty Net = ${totals['d_net']:+,.0f} | GFRE Clean Net = ${totals['c_net']:+,.0f} | DELTA = ${totals['c_net']-totals['d_net']:+,.0f}")
print(f"  Ghost count v1=33 | Ghost count v2={totals['ghosts']}")
print()

# Write CSV
csv_path = "docs/nq_gfre_comparison_v2_fixed.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(results[0].keys()) if results else [])
    w.writeheader()
    w.writerows(results)
print(f"CSV written: {csv_path}")
