"""
scripts/step3_verify_fix_sample.py
===================================
Step 3: Verify the FIX v3.2 on:
  (A) The 10 original Step-1 files
  (B) 20 additional random files from the 19,134-failure set

For each file, report:
  - Whether it now resolves correctly (no false rejection)
  - Outcome category: still-FAIL (genuine), ORPHANED_CLOSE_UNKNOWN_ORIGIN logged,
    ORPHANED_CLOSE_POST_GHOST_OPEN still fired (correct), or PASS

Also re-verifies Jul-09 IPS_TM_7 NQ to confirm no regression.

Usage:
    python scripts/step3_verify_fix_sample.py
"""
import os, sys, sqlite3, re, random, collections

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

STAGING_DB  = os.path.join(PROJECT_ROOT, "trading_platform_clean_v2.db")
DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")
DATE_RE     = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine  import (
    resync, get_rejected_fills, clear_rejected_fills
)

# The 10 Step-1 files (account, date)
STEP1_FILES = [
    ("A_sim7",      "2024-03-15"),
    ("V500_sim13",  "2024-05-05"),
    ("3Q_sim13",    "2024-12-21"),
    ("3Q_sim14",    "2024-12-21"),
    ("3Q_sim15",    "2024-12-21"),
    ("3Q_sim14",    "2024-12-25"),
    ("ES-TS_7",     "2024-06-06"),
    ("ES-TM_7",     "2024-06-16"),
    ("ES_PB_2",     "2024-06-19"),
    ("ES_PB_3",     "2024-06-23"),
]

# Jul-09 confirmation case (had ghosts dropped — guard must still fire)
JUL09_CASE = ("IPS_TM_7", "2026-07-09")


def file_path(account, date):
    return os.path.join(DATASET_DIR,
                        f"TradeActivityLog_{date}_UTC.{account}.data")


def process_file(fpath):
    """Run the FIXED GFRE on one file. Return dict of outcomes."""
    raw, _ = _parse_file_nitro(fpath)
    if not raw:
        return {'n_raw': 0, 'n_ghosts': 0, 'n_trades': 0,
                'integrity_ok': True, 'orphaned_ghost': 0,
                'orphaned_unknown': 0, 'notes': []}
    clear_rejected_fills()
    result   = resync(raw)
    rejected = get_rejected_fills()
    n_ghost_orphan   = sum(1 for r in rejected
                           if r.get('reason') == 'ORPHANED_CLOSE_POST_GHOST_OPEN')
    n_unknown_origin = sum(1 for r in rejected
                           if r.get('reason') == 'ORPHANED_CLOSE_UNKNOWN_ORIGIN')
    return {
        'n_raw'            : result.total_raw_fills,
        'n_ghosts'         : result.ghost_fills_dropped,
        'n_trades'         : len(result.trades),
        'integrity_ok'     : result.integrity_ok,
        'orphaned_ghost'   : n_ghost_orphan,
        'orphaned_unknown' : n_unknown_origin,
        'notes'            : result.notes[-4:],
    }


def classify_outcome(r, expected_class_from_step1=None):
    """Classify file outcome after the fix."""
    if r['orphaned_ghost'] > 0 and r['n_ghosts'] > 0:
        return 'GHOST_ORPHAN_CORRECTLY_REJECTED'   # guard fired correctly (same-day ghost)
    if r['orphaned_unknown'] > 0:
        return 'UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED' # carry-over, logged, not rejected
    if r['integrity_ok']:
        return 'INTEGRITY_PASS'
    return 'INTEGRITY_FAIL_NO_REJECTION'            # genuine failure, not caused by guard


def main():
    random.seed(42)

    db = sqlite3.connect(STAGING_DB)
    db.row_factory = sqlite3.Row

    # Pull 20 random additional failing files (not in Step-1 set)
    step1_set = set(f"{a}/{d}" for a, d in STEP1_FILES)
    all_fails = db.execute("""
        SELECT account, trade_date, total_raw_fills, ghost_fills
        FROM file_audit
        WHERE integrity_ok = 0
        ORDER BY RANDOM()
        LIMIT 200
    """).fetchall()
    additional = []
    for row in all_fails:
        key = f"{row['account']}/{row['trade_date']}"
        if key not in step1_set:
            additional.append((row['account'], row['trade_date'],
                               row['total_raw_fills'], row['ghost_fills']))
        if len(additional) == 20:
            break
    db.close()

    print("=" * 80)
    print("  STEP 3 — FIX v3.2 VERIFICATION SAMPLE")
    print("=" * 80)

    results_a = []
    results_b = []

    # ── Part A: Original 10 Step-1 files ────────────────────────────────────
    print("\n--- Part A: Original 10 Step-1 files ---")
    step1_classifications = {
        "A_sim7/2024-03-15"     : "b_cross_day_carry",
        "V500_sim13/2024-05-05" : "b_cross_day_carry",
        "3Q_sim13/2024-12-21"   : "c_unknown_origin",
        "3Q_sim14/2024-12-21"   : "b_cross_day_carry",
        "3Q_sim15/2024-12-21"   : "c_unknown_origin",
        "3Q_sim14/2024-12-25"   : "b_cross_day_carry",
        "ES-TS_7/2024-06-06"    : "b_cross_day_carry",
        "ES-TM_7/2024-06-16"    : "c_unknown_origin",
        "ES_PB_2/2024-06-19"    : "c_unknown_origin",
        "ES_PB_3/2024-06-23"    : "b_cross_day_carry",
    }

    for account, date in STEP1_FILES:
        fp = file_path(account, date)
        step1_cls = step1_classifications.get(f"{account}/{date}", "?")
        if not os.path.exists(fp):
            print(f"  SKIP {account}/{date} — file not on disk")
            continue
        r = process_file(fp)
        outcome = classify_outcome(r)
        # Expectation: cross-day carries should now show UNKNOWN_ORIGIN_LOGGED,
        # not GHOST_ORPHAN_CORRECTLY_REJECTED (the v3.1 bug).
        correct = (
            (step1_cls == "b_cross_day_carry" and
             outcome == "UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED") or
            (step1_cls == "c_unknown_origin" and
             outcome in ("UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED",
                         "INTEGRITY_FAIL_NO_REJECTION",
                         "INTEGRITY_PASS"))
        )
        ok_str = "OK" if correct else "REGRESSION"
        print(f"  [{ok_str:10s}] {account}/{date}"
              f"  step1={step1_cls[:18]:18s}"
              f"  outcome={outcome}"
              f"  ghosts={r['n_ghosts']}  rejected_ghost={r['orphaned_ghost']}"
              f"  logged_unknown={r['orphaned_unknown']}"
              f"  integrity={'PASS' if r['integrity_ok'] else 'FAIL'}")
        results_a.append({'account': account, 'date': date,
                          'step1_cls': step1_cls, 'outcome': outcome,
                          'correct': correct})

    # ── Jul-09 Regression Check ──────────────────────────────────────────────
    print("\n--- Jul-09 IPS_TM_7 regression check (must still fire guard) ---")
    fp09 = file_path(*JUL09_CASE)
    if os.path.exists(fp09):
        r09 = process_file(fp09)
        fired = r09['orphaned_ghost'] > 0
        print(f"  Account: IPS_TM_7  Date: 2026-07-09")
        print(f"  Ghosts dropped : {r09['n_ghosts']}")
        print(f"  ORPHANED_CLOSE_POST_GHOST_OPEN rejections : {r09['orphaned_ghost']}")
        print(f"  Integrity : {'PASS' if r09['integrity_ok'] else 'FAIL'}")
        print(f"  Guard still fires : {'YES — original fix preserved' if fired else 'NO — REGRESSION!'}")
    else:
        print(f"  SKIP — file not on disk: {fp09}")

    # ── Part B: 20 additional random failing files ───────────────────────────
    print("\n--- Part B: 20 additional random failing files ---")
    outcome_counts = collections.Counter()
    for account, date, raw_fills, ghost_db in additional:
        fp = file_path(account, date)
        if not os.path.exists(fp):
            outcome_counts['SKIP_NOT_ON_DISK'] += 1
            continue
        r = process_file(fp)
        outcome = classify_outcome(r)
        outcome_counts[outcome] += 1
        print(f"  {account:25s} {date}  raw={raw_fills:4d}  ghosts={ghost_db:3d}"
              f"  => {outcome}"
              f"  integrity={'PASS' if r['integrity_ok'] else 'FAIL'}")
        results_b.append({'account': account, 'date': date, 'outcome': outcome,
                          'integrity_ok': r['integrity_ok']})

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  STEP 3 SUMMARY")
    print("=" * 80)

    a_correct = sum(1 for r in results_a if r['correct'])
    print(f"\n  Part A (10 Step-1 files):")
    print(f"    Correctly handled by fix : {a_correct}/{len(results_a)}")
    for r in results_a:
        print(f"      [{r['step1_cls'][:18]:18s}] -> {r['outcome']}")

    print(f"\n  Part B (20 random failing files) — outcome breakdown:")
    for outcome, cnt in sorted(outcome_counts.items()):
        print(f"    {outcome:45s}: {cnt:2d}/20")

    b_resolved   = outcome_counts.get('UNKNOWN_ORIGIN_LOGGED_NOT_REJECTED', 0) + \
                   outcome_counts.get('INTEGRITY_PASS', 0) + \
                   outcome_counts.get('GHOST_ORPHAN_CORRECTLY_REJECTED', 0)
    b_genuine    = outcome_counts.get('INTEGRITY_FAIL_NO_REJECTION', 0)
    print(f"\n    Resolved (guard no longer wrongly rejecting) : {b_resolved}/20")
    print(f"    Genuine integrity failures (not guard-caused) : {b_genuine}/20")

    print("\n  Three-way outcome breakdown across all 30 files:")
    all_outcomes = collections.Counter(r['outcome'] for r in results_a + results_b)
    for o, c in sorted(all_outcomes.items()):
        print(f"    {o:45s}: {c}")


if __name__ == '__main__':
    main()
