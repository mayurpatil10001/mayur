"""
scripts/step1_diagnose_orphaned_close_regression.py
====================================================
Step 1: Confirm or refute the overnight-carry hypothesis.

For each of 10 newly-failing files (6 sim + 4 non-sim):
  1. Find fills rejected as ORPHANED_CLOSE_POST_GHOST_OPEN
  2. Check the prior-day file for that account
  3. Classify as:
     (a) same-day ghost-orphan  - handler correct
     (b) cross-day carry        - handler misclassifies a legitimate carry
     (c) inconclusive / other

API:
    raw, _ = _parse_file_nitro(fpath)     -> raw is list of dicts
    resync(raw)                            -> GFREResult
    get_rejected_fills() / clear_rejected_fills()  -> module-level list

Usage:
    python scripts/step1_diagnose_orphaned_close_regression.py
"""
import os, sys, sqlite3, re, datetime, collections

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

STAGING_DB  = os.path.join(PROJECT_ROOT, "trading_platform_clean_v2.db")
DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")
DATE_RE     = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine  import (
    resync, classify_fill,
    get_rejected_fills, clear_rejected_fills,
    GhostFillEngine,
)


def get_dataset_index():
    """Build {account: sorted [date]} index from dataset dir."""
    idx = collections.defaultdict(list)
    for fname in os.listdir(DATASET_DIR):
        m = DATE_RE.match(fname)
        if m:
            idx[m.group(2)].append(m.group(1))
    for acct in idx:
        idx[acct].sort()
    return idx


def file_path(account, date):
    return os.path.join(DATASET_DIR, f"TradeActivityLog_{date}_UTC.{account}.data")


def run_file(fpath):
    """
    Return (orphaned_fills, same_day_ghosts, raw_fills_count)
    where orphaned_fills = list of rejected-fill dicts with
    reason='ORPHANED_CLOSE_POST_GHOST_OPEN'.
    """
    raw, _ = _parse_file_nitro(fpath)
    if not raw:
        return [], 0, 0
    clear_rejected_fills()
    result   = resync(raw)
    rejected = get_rejected_fills()
    orphaned = [r for r in rejected if r.get('reason') == 'ORPHANED_CLOSE_POST_GHOST_OPEN']
    n_ghosts = result.ghost_fills_dropped
    return orphaned, n_ghosts, len(raw)


def prior_day_net_position(fpath_prior, base_sym):
    """
    Parse prior-day file and compute net ending position for base_sym.
    Returns (net_pos: int, n_fills: int) or (None, 0) on parse failure.
    Positive = net long, negative = net short, 0 = flat.
    Uses raw fill dicts directly (no GFRE) to see the real raw position.
    """
    try:
        raw, _ = _parse_file_nitro(fpath_prior)
    except Exception as e:
        return None, 0

    pos = 0
    n_matching = 0
    for d in raw:
        sym_raw = d.get('symbol', '')
        # Match base_symbol: strip expiry codes (NQM26 -> NQ, ESH25 -> ES)
        bs = re.sub(r'[FGHJKMNQUVXZ]\d{2}$', '', sym_raw).upper()
        if bs != base_sym[:2].upper() and bs != base_sym.upper():
            continue
        side = d.get('side', '')
        qty  = int(d.get('quantity', 0) or 0)
        n_matching += 1
        if side == 'BUY':
            pos += qty
        elif side == 'SELL':
            pos -= qty
    return pos, n_matching


def main():
    print("=" * 80)
    print("  STEP 1 — Overnight-Carry Hypothesis Diagnostic")
    print("=" * 80)

    db = sqlite3.connect(STAGING_DB)
    db.row_factory = sqlite3.Row

    # 6 sim + 4 non-sim smallest-fill failing files
    sim_fails = db.execute("""
        SELECT source_file, account, trade_date, total_raw_fills,
               ghost_fills, bypass_mode, note_coverage, integrity_notes
        FROM file_audit
        WHERE integrity_ok = 0
          AND (account LIKE 'A_sim%' OR account LIKE 'V500_sim%'
               OR account LIKE '3Q_sim%'  OR account LIKE 'V_sim%')
        ORDER BY total_raw_fills ASC
        LIMIT 6
    """).fetchall()

    nonsim_fails = db.execute("""
        SELECT source_file, account, trade_date, total_raw_fills,
               ghost_fills, bypass_mode, note_coverage, integrity_notes
        FROM file_audit
        WHERE integrity_ok = 0
          AND account NOT LIKE 'A_sim%' AND account NOT LIKE 'V500_sim%'
          AND account NOT LIKE '3Q_sim%' AND account NOT LIKE 'V_sim%'
        ORDER BY total_raw_fills ASC
        LIMIT 4
    """).fetchall()

    db.close()

    sample = list(sim_fails) + list(nonsim_fails)
    print(f"\nPulled: {len(sim_fails)} sim-account + {len(nonsim_fails)} non-sim failing files\n")

    dataset_idx = get_dataset_index()
    results     = []

    for row in sample:
        account    = row['account']
        trade_date = row['trade_date']
        raw_fills  = row['total_raw_fills']
        ghosts_db  = row['ghost_fills']
        bypass     = row['bypass_mode']
        notes      = (row['integrity_notes'] or '')[:140]

        print("-" * 70)
        print(f"FILE   : TradeActivityLog_{trade_date}_UTC.{account}.data")
        print(f"Account: {account:<30s}  Date: {trade_date}")
        print(f"DB     : raw={raw_fills} ghosts={ghosts_db} bypass={bypass}")
        print(f"Notes  : {notes}")

        fp = file_path(account, trade_date)
        if not os.path.exists(fp):
            print("  [SKIP] File not found on disk")
            results.append({'account': account, 'date': trade_date,
                            'classification': 'SKIP_NOT_ON_DISK'})
            continue

        orphaned, same_day_ghosts, n_raw = run_file(fp)
        print(f"Live   : raw={n_raw}  same-day ghosts dropped={same_day_ghosts}"
              f"  ORPHANED_CLOSE rejections={len(orphaned)}")

        for i, orf in enumerate(orphaned[:3]):
            print(f"  Rej {i+1}: {orf.get('side','?')} {orf.get('quantity','?')}x "
                  f"{orf.get('symbol','?')} @ {orf.get('timestamp','?')}")

        # Prior-day lookup
        dates = dataset_idx.get(account, [])
        try:
            pos_in_dates = dates.index(trade_date)
        except ValueError:
            pos_in_dates = -1

        if pos_in_dates <= 0:
            print("  Prior  : NO PRIOR FILE in dataset for this account")
            classification = 'c_no_prior_file'
        else:
            prior_date = dates[pos_in_dates - 1]
            d_cur   = datetime.date.fromisoformat(trade_date)
            d_prior = datetime.date.fromisoformat(prior_date)
            gap     = (d_cur - d_prior).days
            fp_prior = file_path(account, prior_date)

            if not os.path.exists(fp_prior):
                print(f"  Prior  : {prior_date} — FILE NOT ON DISK")
                classification = 'c_prior_file_missing'
            else:
                # Compute prior-day ending position for each orphaned symbol
                classification_votes = []
                for orf in (orphaned[:2] if orphaned else [{'base_symbol': '?', 'symbol': '?'}]):
                    orf_bs = orf.get('base_symbol') or re.sub(
                        r'[FGHJKMNQUVXZ]\d{2}$', '', orf.get('symbol', '')).upper()
                    prior_pos, n_prior_sym_fills = prior_day_net_position(fp_prior, orf_bs)
                    print(f"  Prior  : {prior_date} (gap={gap}d)  "
                          f"net_pos({orf_bs})={prior_pos:+d} "
                          f"prior_sym_fills={n_prior_sym_fills}")

                    if prior_pos is None:
                        classification_votes.append('c_prior_parse_error')
                    elif prior_pos != 0 and same_day_ghosts == 0:
                        print(f"    -> Prior NON-FLAT, no same-day ghosts. "
                              f"CROSS-DAY CARRY misclassified as orphaned. BUG.")
                        classification_votes.append('b_cross_day_carry')
                    elif prior_pos != 0 and same_day_ghosts > 0:
                        print(f"    -> Prior NON-FLAT AND same-day ghosts exist. AMBIGUOUS.")
                        classification_votes.append('c_ambiguous_both')
                    elif prior_pos == 0 and same_day_ghosts > 0:
                        print(f"    -> Prior FLAT, same-day ghosts removed. Handler CORRECT.")
                        classification_votes.append('a_same_day_ghost_orphan')
                    else:  # prior_pos == 0 and same_day_ghosts == 0
                        if len(orphaned) == 0:
                            print(f"    -> No ORPHANED rejections. Integrity failure has different cause.")
                            classification_votes.append('c_no_orphaned_rejection')
                        else:
                            print(f"    -> Prior FLAT, NO same-day ghosts. UNKNOWN ORIGIN.")
                            classification_votes.append('c_unknown_origin')

                # Majority vote
                if classification_votes:
                    classification = collections.Counter(classification_votes).most_common(1)[0][0]
                else:
                    classification = 'c_no_orphaned_fills'

        print(f"  CLASS  : {classification}")
        results.append({
            'account': account, 'date': trade_date, 'raw_fills': raw_fills,
            'same_day_ghosts': same_day_ghosts if 'same_day_ghosts' in dir() else 0,
            'orphaned': len(orphaned) if 'orphaned' in dir() else 0,
            'classification': classification,
        })

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("  STEP 1 — SUMMARY")
    print("=" * 80)
    counts = collections.Counter(r['classification'] for r in results)
    total  = len(results)
    for cls, cnt in sorted(counts.items()):
        print(f"  {cls:55s}: {cnt:2d}/{total}")
    print()
    print("  Individual results:")
    for r in results:
        print(f"    [{r['classification']:35s}] {r['account']} / {r['date']} "
              f"(raw={r['raw_fills']}, orphaned={r['orphaned']})")

    a = counts.get('a_same_day_ghost_orphan', 0)
    b = counts.get('b_cross_day_carry', 0)
    c = total - a - b

    print(f"\n  (a) Same-day ghost-orphan [handler CORRECT] : {a}/{total}")
    print(f"  (b) Cross-day carry misclassified [BUG]     : {b}/{total}")
    print(f"  (c) Inconclusive / other                    : {c}/{total}")

    print()
    if b >= total // 2:
        print("  => OVERNIGHT-CARRY HYPOTHESIS SUPPORTED. Evidence justifies Step 2 design.")
    elif b == 0 and a > 0:
        print("  => HYPOTHESIS REFUTED. Handler appears correct; investigate alternate cause.")
    elif b > 0 and a > 0:
        print("  => MIXED EVIDENCE. Both mechanisms present; design must handle both.")
    else:
        print("  => INCONCLUSIVE. Stop and investigate before designing any fix.")


if __name__ == '__main__':
    main()
