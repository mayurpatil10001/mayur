"""Fast targeted verification: pick 5 specific IPS_TM_7 files we KNOW have fills."""
import sys, os, glob
sys.path.insert(0, '.')
from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, pair_fills_to_trades
)

# 1. Thread vs direct diagnosis on ONE known file
import concurrent.futures

known_fp = "dataset/TradeActivityLog_2026-07-09_UTC.IPS_TM_7.data"
print(f"Test file: {os.path.basename(known_fp)}  size={os.path.getsize(known_fp)/1024:.0f}KB")

# Direct
raw_d, _ = _parse_file_nitro(known_fp)
print(f"Direct call: {len(raw_d)} raw records")

# Thread
def _t(fp):
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(fp), '..', '..'))
    from trading_platform.services.binary_log_parser import _parse_file_nitro as p
    r, _ = p(fp)
    return len(r)

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    fut = ex.submit(_t, os.path.abspath(known_fp))
    n_t = fut.result()
print(f"Thread call: {n_t} raw records")

print()
print("="*60)
print("DIRECT VERIFICATION: 5 IPS_TM_7 files")
print("="*60)

test_files = [
    "dataset/TradeActivityLog_2026-07-09_UTC.IPS_TM_7.data",
    "dataset/TradeActivityLog_2026-07-02_UTC.IPS_TM_7.data",
    "dataset/TradeActivityLog_2026-06-23_UTC.IPS_TM_7.data",
    "dataset/TradeActivityLog_2026-06-10_UTC.IPS_TM_7.data",
    "dataset/TradeActivityLog_2026-06-02_UTC.IPS_TM_7.data",
]

total_raw = total_ghosts = total_clean = total_trades = 0
for fp in test_files:
    if not os.path.exists(fp):
        print(f"  MISSING: {fp}")
        continue
    raw, _ = _parse_file_nitro(fp)
    if not raw:
        print(f"  {os.path.basename(fp)}: 0 fills")
        continue
    fills = GhostFillEngine.from_dicts(raw)
    n_raw = len(fills)
    ghosts = [f for f in fills if classify_fill(f)]
    clean  = [f for f in fills if not classify_fill(f)]
    trades, _ = pair_fills_to_trades(clean)
    dirty_f = GhostFillEngine.from_dicts(raw)
    for df in dirty_f: df.suggests_ghost = False
    dt, _ = pair_fills_to_trades(list(dirty_f))
    dirty_net = sum(t.pnl_dollars for t in dt)
    clean_net = sum(t.pnl_dollars for t in trades)
    total_raw += n_raw
    total_ghosts += len(ghosts)
    total_clean += len(clean)
    total_trades += len(trades)
    print(f"  {os.path.basename(fp)}")
    print(f"    raw={n_raw}  ghosts={len(ghosts)}  clean_fills={len(clean)}  trades={len(trades)}")
    print(f"    dirty=${dirty_net:+,.2f}  clean=${clean_net:+,.2f}  delta=${clean_net-dirty_net:+,.2f}")

print()
print(f"TOTALS: raw={total_raw}  ghosts={total_ghosts}  clean_fills={total_clean}  trades={total_trades}")
ghost_rate = 100*total_ghosts/total_raw if total_raw else 0
print(f"Ghost rate: {ghost_rate:.2f}%")
print()

# 2. Check DB state
import sqlite3
db = "trading_platform_clean_v2.db"
if os.path.exists(db):
    con = sqlite3.connect(db)
    n_audit = con.execute("SELECT COUNT(*) FROM file_audit").fetchone()[0]
    n_raw_db = con.execute("SELECT SUM(total_raw_fills) FROM file_audit").fetchone()[0] or 0
    n_g_db = con.execute("SELECT SUM(ghost_fills) FROM file_audit").fetchone()[0] or 0
    n_ct = con.execute("SELECT COUNT(*) FROM clean_trades").fetchone()[0]
    con.close()
    print(f"Staging DB:")
    print(f"  file_audit rows : {n_audit:,}")
    print(f"  raw fills total : {n_raw_db:,}")
    print(f"  ghost fills     : {n_g_db:,}")
    print(f"  clean_trades    : {n_ct:,}")
    if n_raw_db == 0:
        print()
        print("  ISSUE: DB shows 0 raw fills — ThreadPoolExecutor in cleaner")
        print("  could not import binary_log_parser in worker threads.")
        print("  FIX: re-run ghost_fill_cleaner with --workers 1 (single-threaded)")
        print("       OR call sys.path.insert(0, PROJECT_ROOT) inside worker fn")
