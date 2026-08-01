"""
verify_ghost_clean.py
Verifies ghost fill removal by:
1. Checking what _parse_file_nitro actually returns per file type
2. Running direct (single-threaded) parse on known-fill accounts
3. Querying the staging DB for results
4. Computing ghost rate from a direct sample run
"""
import sys, os, glob, re, sqlite3
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, pair_fills_to_trades, verify_sequence
)

DATE_RE = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')

print("="*65)
print("GHOST FILL VERIFICATION REPORT")
print("="*65)

# --- 1. Check staging DB ---
DB = os.path.join(os.path.dirname(__file__), '..', 'trading_platform_clean_v2.db')
if os.path.exists(DB):
    con = sqlite3.connect(DB)
    n_trades  = con.execute("SELECT COUNT(*) FROM clean_trades").fetchone()[0]
    n_audit   = con.execute("SELECT COUNT(*) FROM file_audit").fetchone()[0]
    n_flagged = con.execute("SELECT COUNT(*) FROM file_audit WHERE flagged=1").fetchone()[0]
    n_ghosts_db = con.execute("SELECT SUM(ghost_fills) FROM file_audit").fetchone()[0] or 0
    n_raw_db    = con.execute("SELECT SUM(total_raw_fills) FROM file_audit").fetchone()[0] or 0
    n_int_fail  = con.execute("SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0").fetchone()[0]
    con.close()

    print(f"\n[1] Staging DB: trading_platform_clean_v2.db")
    print(f"    file_audit rows    : {n_audit:,}")
    print(f"    clean_trades rows  : {n_trades:,}")
    print(f"    raw fills total    : {n_raw_db:,}")
    print(f"    ghost fills removed: {n_ghosts_db:,}")
    print(f"    flagged files      : {n_flagged}")
    print(f"    integrity failures : {n_int_fail}")
    if n_raw_db == 0:
        print(f"    STATUS: raw_fills=0 — parser returned empty for all files in threaded mode")
else:
    print(f"\n[1] DB not found: {DB}")

# --- 2. Direct parse of known accounts (single-threaded, ground truth) ---
print(f"\n[2] Direct single-threaded parse on known-fill accounts")
print(f"    (This is the authoritative result — no threading issues)")

KNOWN_FILL_ACCOUNTS = [
    "IPS_TM_7", "IPS_TM_3", "IPS_TM_5", "TM_7", "TM_5",
    "PB_1", "PB_2", "ES-IPS_TM_7", "CL-IPS_TM_7", "TM_8"
]

dataset_dir = os.path.join(os.path.dirname(__file__), '..', 'dataset')
total_raw = total_ghosts = total_clean = total_trades = 0
files_with_fills = 0
files_checked = 0
errors = 0
ghost_details = []

for acct in KNOWN_FILL_ACCOUNTS:
    fps = sorted(glob.glob(os.path.join(dataset_dir, f"*.{acct}.data")))
    fps = [f for f in fps if os.path.getsize(f) > 5000]  # skip stubs
    # sample 20 files per account spanning different months
    sample = fps[::max(1, len(fps)//20)][:20]

    for fp in sample:
        fname = os.path.basename(fp)
        m = DATE_RE.match(fname)
        if not m:
            continue
        yr = int(m.group(1)[:4])
        if yr < 2020 or yr > 2030:
            continue
        files_checked += 1
        try:
            raw, _ = _parse_file_nitro(fp)
            if not raw:
                continue
            fills = GhostFillEngine.from_dicts(raw)
            if not fills:
                continue

            n_raw = len(fills)
            ghosts = [f for f in fills if classify_fill(f)]
            clean  = [f for f in fills if not classify_fill(f)]
            trades, _ = pair_fills_to_trades(clean)
            dirty_f = list(GhostFillEngine.from_dicts(raw))
            for df in dirty_f: df.suggests_ghost = False
            dirty_trades, _ = pair_fills_to_trades(dirty_f)
            dirty_net = sum(t.pnl_dollars for t in dirty_trades)
            clean_net = sum(t.pnl_dollars for t in trades)

            total_raw    += n_raw
            total_ghosts += len(ghosts)
            total_clean  += len(clean)
            total_trades += len(trades)
            files_with_fills += 1

            if ghosts:
                ghost_details.append((fname, acct, n_raw, len(ghosts), dirty_net, clean_net))

        except Exception as e:
            errors += 1
            print(f"    ERROR: {fname}: {e}")

ghost_rate = 100 * total_ghosts / total_raw if total_raw > 0 else 0

print(f"    Accounts checked   : {len(KNOWN_FILL_ACCOUNTS)}")
print(f"    Files checked      : {files_checked}")
print(f"    Files with fills   : {files_with_fills}")
print(f"    Parse errors       : {errors}")
print(f"    Total raw fills    : {total_raw:,}")
print(f"    Ghost fills found  : {total_ghosts:,}  ({ghost_rate:.2f}%)")
print(f"    Clean fills kept   : {total_clean:,}")
print(f"    Clean trades out   : {total_trades:,}")

if total_ghosts > 0:
    print(f"\n    Files with ghosts ({len(ghost_details)}):")
    for fname, acct, n_raw, n_g, dn, cn in sorted(ghost_details, key=lambda x: -x[3])[:15]:
        print(f"      {fname}  raw={n_raw}  ghosts={n_g}  dirty=${dn:+,.0f}  clean=${cn:+,.0f}  delta=${cn-dn:+,.0f}")
else:
    print(f"\n    No ghost fills found in this sample.")

# --- 3. Diagnosis of why threading returned 0 ---
print(f"\n[3] Thread vs single-thread parse comparison")
test_fp = None
for acct in KNOWN_FILL_ACCOUNTS:
    fps = sorted(glob.glob(os.path.join(dataset_dir, f"*.{acct}.data")))
    fps = [f for f in fps if os.path.getsize(f) > 50000]
    if fps:
        test_fp = fps[0]
        break

if test_fp:
    print(f"    Test file: {os.path.basename(test_fp)}")
    # Direct call
    raw_direct, _ = _parse_file_nitro(test_fp)
    print(f"    Direct call result : {len(raw_direct)} fills")

    import concurrent.futures
    def _t(fp):
        r, _ = _parse_file_nitro(fp)
        return len(r)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fut = ex.submit(_t, test_fp)
        n_thread = fut.result()
    print(f"    Thread call result : {n_thread} fills")

    if n_thread == 0 and len(raw_direct) > 0:
        print(f"    DIAGNOSIS: ThreadPoolExecutor returns 0 — import/path issue in worker thread")
        print(f"    FIX NEEDED: cleaner must be run single-threaded OR with proper sys.path in worker")
    else:
        print(f"    Thread and direct agree. Parser is consistent.")

print(f"\n{'='*65}")
print(f"VERIFICATION COMPLETE")
print(f"{'='*65}")
