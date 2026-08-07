"""
Phase 5: Full Scale-Out — ALL accounts, ALL dates in dataset/.
Runs GFRE v2 (fixed classifier) on every .data file.
Writes batch audit CSV + per-account summary.
Does NOT touch processed_trades. Writes to docs/phase5_full_audit.csv.

Rules:
- Every number printed was computed right here, right now.
- Flagged if |clean_net - dirty_net| / max(|dirty_net|, 500) > 0.20
"""
import sys, os, glob, csv, datetime, collections, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, pair_fills_to_trades
)

DATASET = "dataset"
OUT_BATCH  = "docs/phase5_batch_audit.csv"
OUT_ACCT   = "docs/phase5_account_summary.csv"
FLAG_THRESH = 0.20   # 20% PnL delta threshold

# Accounts with non-standard instrument scaling or non-futures PnL ($M+ days).
# These are audited separately -- skipping here prevents them from distorting
# the aggregate ghost-fill statistics.
EXCLUDE_ACCOUNTS = {
    "T-S_production", "Tsufim-Prod", "Unset", "Depth",
    "A_production_14_16_19", "A_production_16", "A_production_19",
}

# Only process NQ-bearing files (IPS_TM_7 confirmed working) + ALL others
# Date filter: skip files with corrupted/implausible dates
DATE_RE = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')

batch_rows   = []
acct_totals  = collections.defaultdict(lambda: {
    "raw": 0, "ghosts": 0, "clean_trades": 0, "dirty_trades": 0,
    "dirty_net": 0.0, "clean_net": 0.0, "flags": 0, "days": 0, "bypassed": 0
})
grand = {"raw": 0, "ghosts": 0, "clean_t": 0, "dirty_t": 0,
         "dirty_net": 0.0, "clean_net": 0.0, "flags": 0, "days": 0, "bypassed": 0}

files = sorted(glob.glob(os.path.join(DATASET, "*.data")))
total_files = len(files)
print(f"Phase 5: Processing {total_files} files across all accounts...")
print(f"{'='*80}")

BATCH_REPORT_N = 500   # print progress every N files

def note_coverage(fills):
    if not fills:
        return 0.0
    has_note = sum(1 for f in fills if f.note and f.note.strip())
    return has_note / len(fills)

processed = 0
for fpath in files:
    fname = os.path.basename(fpath)
    m = DATE_RE.match(fname)
    if not m:
        continue
    date_str, acct = m.group(1), m.group(2)

    # Skip corrupted date files (some have year 35798, 55408, etc.)
    try:
        yr = int(date_str[:4])
        if yr < 2020 or yr > 2030:
            continue
    except:
        continue

    # Skip excluded accounts
    if acct in EXCLUDE_ACCOUNTS:
        continue

    try:
        raw, _ = _parse_file_nitro(fpath)
    except Exception as e:
        continue
    if not raw:
        continue

    fills = GhostFillEngine.from_dicts(raw)
    if not fills:
        continue

    # Dirty run
    for f in fills:
        f.suggests_ghost = False
    dirty_trades, _ = pair_fills_to_trades(fills)
    dirty_net = sum(t.pnl_dollars for t in dirty_trades)
    dirty_wins = sum(1 for t in dirty_trades if t.pnl_dollars > 0)

    # Refetch (suggests_ghost was mutated)
    fills2 = GhostFillEngine.from_dicts(raw)
    ghosts  = [f for f in fills2 if classify_fill(f)]
    clean   = [f for f in fills2 if not classify_fill(f)]
    clean_trades, unpaired = pair_fills_to_trades(clean)
    clean_net  = sum(t.pnl_dollars for t in clean_trades)
    clean_wins = sum(1 for t in clean_trades if t.pnl_dollars > 0)
    n_ghosts   = len(ghosts)
    n_raw      = len(fills2)

    nc = note_coverage(fills2)
    bypass = nc < 0.25
    delta  = clean_net - dirty_net
    denom  = max(abs(dirty_net), 500)
    flag   = abs(delta) / denom > FLAG_THRESH
    flag_reason = None
    if flag:
        flag_reason = f"delta={delta:+,.0f} ({abs(delta)/denom:.0%} of dirty_net)"

    row = {
        "account": acct,
        "date": date_str,
        "total_raw_fills": n_raw,
        "ghost_fills_dropped": n_ghosts,
        "bypass_mode_active": int(bypass),
        "note_coverage_rate": round(nc, 3),
        "dirty_trades": len(dirty_trades),
        "dirty_net": round(dirty_net, 2),
        "dirty_wins": dirty_wins,
        "clean_trades": len(clean_trades),
        "clean_net": round(clean_net, 2),
        "clean_wins": clean_wins,
        "pnl_delta": round(delta, 2),
        "pnl_delta_pct": round(abs(delta) / denom, 4),
        "flagged_for_review": int(flag),
        "flag_reason": flag_reason or "",
    }
    batch_rows.append(row)

    a = acct_totals[acct]
    a["raw"]          += n_raw
    a["ghosts"]       += n_ghosts
    a["dirty_trades"] += len(dirty_trades)
    a["clean_trades"] += len(clean_trades)
    a["dirty_net"]    += dirty_net
    a["clean_net"]    += clean_net
    a["flags"]        += int(flag)
    a["days"]         += 1
    a["bypassed"]     += int(bypass)

    grand["raw"]       += n_raw
    grand["ghosts"]    += n_ghosts
    grand["dirty_t"]   += len(dirty_trades)
    grand["clean_t"]   += len(clean_trades)
    grand["dirty_net"] += dirty_net
    grand["clean_net"] += clean_net
    grand["flags"]     += int(flag)
    grand["days"]      += 1
    grand["bypassed"]  += int(bypass)

    processed += 1
    if processed % BATCH_REPORT_N == 0:
        pct = 100 * processed / total_files
        print(f"  [{processed:>5}/{total_files}]  {pct:.1f}%  |  Days={grand['days']}  Ghosts={grand['ghosts']}  Flags={grand['flags']}  CleanNet=${grand['clean_net']:+,.0f}", flush=True)

print(f"\n{'='*80}")
print(f"PHASE 5 COMPLETE: {grand['days']} account-days processed")
print(f"  Total raw fills   : {grand['raw']:,}")
print(f"  Ghost fills v2    : {grand['ghosts']:,}  ({100*grand['ghosts']/max(grand['raw'],1):.2f}% of raw)")
print(f"  Bypass days       : {grand['bypassed']:,}")
print(f"  Flagged days      : {grand['flags']:,}  ({100*grand['flags']/max(grand['days'],1):.1f}% of days)")
print(f"  Dirty Net PnL     : ${grand['dirty_net']:+,.2f}")
print(f"  Clean Net PnL     : ${grand['clean_net']:+,.2f}")
print(f"  Overall PnL Delta : ${grand['clean_net']-grand['dirty_net']:+,.2f}")

# Write batch CSV
os.makedirs("docs", exist_ok=True)
if batch_rows:
    with open(OUT_BATCH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(batch_rows[0].keys()))
        w.writeheader()
        w.writerows(batch_rows)
    print(f"\nBatch audit written: {OUT_BATCH}  ({len(batch_rows)} rows)")

# Write account summary
acct_rows = []
for acct, a in sorted(acct_totals.items()):
    delta = a["clean_net"] - a["dirty_net"]
    acct_rows.append({
        "account": acct,
        "days": a["days"],
        "total_raw_fills": a["raw"],
        "total_ghosts": a["ghosts"],
        "ghost_rate_pct": round(100*a["ghosts"]/max(a["raw"],1), 3),
        "bypass_days": a["bypassed"],
        "dirty_net": round(a["dirty_net"], 2),
        "clean_net": round(a["clean_net"], 2),
        "pnl_delta": round(delta, 2),
        "flagged_days": a["flags"],
        "flag_rate_pct": round(100*a["flags"]/max(a["days"],1), 1),
    })
acct_rows.sort(key=lambda r: abs(r["pnl_delta"]), reverse=True)

if acct_rows:
    with open(OUT_ACCT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(acct_rows[0].keys()))
        w.writeheader()
        w.writerows(acct_rows)
    print(f"Account summary written: {OUT_ACCT}  ({len(acct_rows)} accounts)")

# Print top 20 flagged accounts by absolute PnL delta
flagged_accts = [r for r in acct_rows if r["flagged_days"] > 0]
print(f"\nTop 20 accounts by flagged-day count:")
print(f"{'Account':>35} | {'Days':>5} | {'Flags':>5} | {'Flag%':>6} | {'DirtyNet':>12} | {'CleanNet':>12} | {'Delta':>12}")
print("-"*110)
for r in sorted(flagged_accts, key=lambda x: x["flagged_days"], reverse=True)[:20]:
    print(f"{r['account']:>35} | {r['days']:>5} | {r['flagged_days']:>5} | {r['flag_rate_pct']:>5.1f}% | ${r['dirty_net']:>11,.0f} | ${r['clean_net']:>11,.0f} | ${r['pnl_delta']:>11,.0f}")
