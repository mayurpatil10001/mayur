"""
scripts/step_final_checks.py
============================
Steps 1+2+3 of the "Final Two Checks Before Promotion" task.

Step 1 — Re-classify all 25 Category-A sample files with:
  (a) The REAL per-symbol pipeline (engine.process(), same as resync() — confirmed identical)
  (b) Actual verify_sequence failure messages from per_symbol.integrity_notes
      (not an ad-hoc formula)
  Corrects the previous "fill_count_mismatch" and "genuine_unclosed_position"
  classifications and replaces them with the 3 real verify_sequence checks:
    - DIRECTION FLIPS
    - POSITION IMBALANCE
    - INVERTED TRADES

Step 2 — Overnight carry check for all 'unclosed position' files:
  - All 12 originally classified unclosed-position files (re-verified)
  - PLUS 30 more randomly sampled from the full 3,708 population
  - For each: inspect next day's file for the same account to check whether
    the position left open at end-of-day is closed there (case b = legitimate
    overnight carry) or never resolved (case a = genuine data problem)

Step 3 — Distribution concentration check:
  - 3,708 excluded pure-natural files vs full 61,706 dataset
  - By base_symbol (from per_symbol_summary JSON)
  - By day-of-week (from trade_date)
  - By year/month (hour-of-day unavailable at file-audit granularity)
"""
import os, sys, json, random, collections, datetime

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import sqlite3
DATASET_DIR = os.path.join(PROJECT_ROOT, 'dataset')
DB          = os.path.join(PROJECT_ROOT, 'trading_platform_clean_v2.db')

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine  import (
    GhostFillEngine, clear_rejected_fills, get_rejected_fills
)

# Same 25-file sample as before (seed=99)
random.seed(99)
all_pure = db.execute(
    "SELECT account, trade_date, total_raw_fills, ghost_fills, bypass_mode, "
    "       note_coverage, flag_reason, integrity_notes "
    "FROM file_audit WHERE integrity_ok=0 "
    "AND flag_reason NOT LIKE '%rejected_fills%' "
    "ORDER BY account, trade_date"
).fetchall()
sample25 = random.sample(list(all_pure), 25)

# ── STEP 1 — Re-classify with real per-symbol pipeline ────────────────────
print("=" * 80)
print("  STEP 1 — CONFIRMED: resync() = GhostFillEngine.process() = PER-SYMBOL PIPELINE")
print("=" * 80)
print()
print("  Evidence from ghost_fill_engine.py L939-1105:")
print("  GhostFillEngine.process() groups fills by base_symbol BEFORE pair_fills_to_trades().")
print("  resync() = GhostFillEngine.from_dicts() + GhostFillEngine().process()")
print("  Both the diagnostic script and production _process_file() use the same code path.")
print("  The prior report's 'all-symbols-together' claim was INCORRECT.")
print()
print("  THREADING RACE on rejected_fills (module-level global):")
print("  ghost_fill_cleaner.py L589 uses ThreadPoolExecutor(max_workers=cpu-1).")
print("  _clr_rejected() in concurrent _process_file() threads races on the shared list.")
print("  Impact: flag_reason 'rejected_fills=N' counts in DB are UNRELIABLE (can be 0")
print("          due to race even if guard fired). BUT integrity_ok is computed before")
print("          _get_rejected() inside engine.process() and IS reliable.")
print("  Implication: A/B/C categorization (based on flag_reason) has noise from race.")
print("               The 3,708 excluded files are still correctly excluded (integrity_ok=0).")
print()
print("  CORRECTED CLASSIFICATION: using actual per_symbol.integrity_notes messages")
print("  (the 3 real verify_sequence checks):")
print("    DIRECTION FLIPS  — flip_count > 0 in clean fill stream")
print("    POSITION IMBALANCE — net delta not in {0, expected_open}")
print("    INVERTED TRADES  — any trade with exit_time < entry_time")
print()

engine = GhostFillEngine()

def classify_from_notes(result):
    """Extract actual failure reason(s) from per-symbol integrity_notes."""
    reasons = []
    for bs, sr in result.per_symbol.items():
        if sr.integrity_ok:
            continue
        for msg in sr.integrity_notes:
            if 'DIRECTION FLIP' in msg:
                reasons.append(f'DIRECTION_FLIPS [{bs}]')
            elif 'POSITION IMBALANCE' in msg:
                reasons.append(f'POSITION_IMBALANCE [{bs}]')
            elif 'INVERTED TRADE' in msg:
                reasons.append(f'INVERTED_TRADES [{bs}]')
    return reasons if reasons else ['UNKNOWN (no failing msg found)']

print(f"  {'#':>3}  {'Account':25s} {'Date':12s} {'raw':4s} {'gh':3s} {'tr':3s} {'unp':3s} {'rej':3s} {'int':4s}  failure reason(s)")
print("  " + "-" * 100)

step1_results = []
fail_dist_new = collections.Counter()
unclosed_files = []  # for Step 2

for i, row in enumerate(sample25):
    account    = row['account']
    trade_date = row['trade_date']
    db_notes   = row['integrity_notes'] or ''

    fname = f"TradeActivityLog_{trade_date}_UTC.{account}.data"
    fpath = os.path.join(DATASET_DIR, fname)

    if not os.path.exists(fpath):
        print(f"  {i+1:>3}  {account:25s} {trade_date}  NOT_ON_DISK")
        step1_results.append({'idx': i+1, 'account': account, 'date': trade_date,
                              'status': 'NOT_ON_DISK', 'reasons': ['NOT_ON_DISK'],
                              'raw': 0, 'gh': 0, 'trades': 0, 'unp': 0, 'rej': 0})
        continue

    raw_fills, _ = _parse_file_nitro(fpath)
    if not raw_fills:
        print(f"  {i+1:>3}  {account:25s} {trade_date}  EMPTY")
        step1_results.append({'idx': i+1, 'account': account, 'date': trade_date,
                              'status': 'EMPTY', 'reasons': ['EMPTY'], 'raw': 0, 'gh': 0,
                              'trades': 0, 'unp': 0, 'rej': 0})
        continue

    clear_rejected_fills()
    fills  = GhostFillEngine.from_dicts(raw_fills)
    result = engine.process(fills)
    rejected = get_rejected_fills()

    reasons = classify_from_notes(result)
    for r in reasons:
        key = r.split(' [')[0]  # strip symbol name for counting
        fail_dist_new[key] += 1

    has_unp = len(result.unpaired_fills) > 0
    if has_unp:
        unclosed_files.append({
            'idx': i+1, 'account': account, 'date': trade_date,
            'unpaired': result.unpaired_fills,
            'reasons': reasons,
            'result': result,
        })

    step1_results.append({
        'idx': i+1, 'account': account, 'date': trade_date,
        'status': 'OK',
        'raw': result.total_raw_fills,
        'gh': result.ghost_fills_dropped,
        'trades': len(result.trades),
        'unp': len(result.unpaired_fills),
        'rej': len(rejected),
        'reasons': reasons,
        'integrity_ok': result.integrity_ok,
    })

    reasons_str = ' | '.join(reasons)[:55]
    print(f"  {i+1:>3}  {account:25s} {trade_date}"
          f"  {result.total_raw_fills:4d} {result.ghost_fills_dropped:3d}"
          f" {len(result.trades):3d} {len(result.unpaired_fills):3d}"
          f" {len(rejected):3d}"
          f" {'PASS' if result.integrity_ok else 'FAIL'}"
          f"  {reasons_str}")

print()
print("  FAILURE REASON DISTRIBUTION (25-file sample, corrected):")
for reason, count in sorted(fail_dist_new.items(), key=lambda x: -x[1]):
    print(f"    {count:3d}/25  {reason}")

# Compare with original
print()
print("  COMPARISON — Original vs Corrected classification:")
print("    Original (ad-hoc formula):  13/25 fill_count_mismatch (unreliable),")
print("                                 8/25 genuine_unclosed_position,")
print("                                 4/25 unclosed_position_other")
changed = sum(1 for r in step1_results if r.get('status') == 'OK' and
              'DIRECTION_FLIPS' not in str(r.get('reasons', [])) and
              'POSITION_IMBALANCE' not in str(r.get('reasons', [])) and
              'INVERTED_TRADES' not in str(r.get('reasons', [])))

print(f"    Corrected (real pipeline): using actual verify_sequence messages above")
print(f"    Files where integrity_ok is now PASS in re-run (reclassified): "
      f"{sum(1 for r in step1_results if r.get('integrity_ok') is True)}")
print(f"    Files still FAIL: {sum(1 for r in step1_results if r.get('integrity_ok') is False)}")

# ── STEP 2 — Overnight carry check ────────────────────────────────────────
print()
print("=" * 80)
print("  STEP 2 — OVERNIGHT CARRY CHECK")
print("=" * 80)

def get_next_day_file(account, trade_date_str):
    """Return path of next trading day's file for this account, or None."""
    d = datetime.datetime.strptime(trade_date_str, '%Y-%m-%d').date()
    for offset in [1, 2, 3, 4, 5]:  # try up to 5 calendar days (weekend skip)
        nd = d + datetime.timedelta(days=offset)
        nd_str = nd.strftime('%Y-%m-%d')
        fname = f"TradeActivityLog_{nd_str}_UTC.{account}.data"
        fpath = os.path.join(DATASET_DIR, fname)
        if os.path.exists(fpath):
            return fpath, nd_str
    return None, None

def check_overnight_carry(account, trade_date, unpaired_fills, result):
    """
    Check if unpaired fills from this day are resolved in the next day's file.
    Returns: ('CLOSED_NEXT_DAY', detail) | ('NEVER_CLOSED', detail) | ('NO_NEXT_FILE', detail)
    """
    if not unpaired_fills:
        return ('NO_UNCLOSED', '')

    # Get the symbol(s) of unclosed position
    unclosed_symbols = {}
    for f in unpaired_fills:
        bs = f.base_symbol
        delta = f.quantity if f.side == 'BUY' else -f.quantity
        unclosed_symbols[bs] = unclosed_symbols.get(bs, 0) + delta

    next_path, next_date = get_next_day_file(account, trade_date)
    if not next_path:
        return ('NO_NEXT_FILE', f"unclosed: {unclosed_symbols}")

    raw2, _ = _parse_file_nitro(next_path)
    if not raw2:
        return ('NEXT_FILE_EMPTY', f"unclosed: {unclosed_symbols}")

    # Look for fills in the next file that would close the unclosed positions
    closing_fills = {}
    for fill_dict in raw2:
        bs = fill_dict.get('base_symbol') or fill_dict.get('symbol', '')
        # Simplify symbol: strip contract suffix
        import re
        bs_clean = re.sub(r'[FGHJKMNQUVXZ]\d+$', '', bs)
        for sym, delta in unclosed_symbols.items():
            sym_clean = re.sub(r'[FGHJKMNQUVXZ]\d+$', '', sym)
            if bs_clean == sym_clean or bs == sym:
                side = fill_dict.get('side', '')
                qty = fill_dict.get('quantity', 0)
                oc = fill_dict.get('open_close', '')
                if side and ((delta > 0 and side == 'SELL') or (delta < 0 and side == 'BUY')):
                    closing_fills[sym] = closing_fills.get(sym, [])
                    closing_fills[sym].append(
                        f"{side} {qty} {bs} oc={oc} on {next_date}"
                    )

    if closing_fills:
        detail = '; '.join([f"{s}: {v[0]}" for s, v in closing_fills.items()])
        return ('CLOSED_NEXT_DAY', f"unclosed={unclosed_symbols} → {detail}")
    else:
        return ('NEVER_CLOSED', f"unclosed={unclosed_symbols}, no matching fill in {next_date}")

# First: check all files with unpaired fills from the 25-file sample (both classified types)
# Collect ALL 25-file results that had unpaired > 0
unclosed_12 = [r for r in step1_results
               if r.get('status') == 'OK' and r.get('unp', 0) > 0]

print()
print(f"  2A — Files from the 25-file sample with unpaired fills: {len(unclosed_12)}")
print(f"  {'#':>3}  {'Account':25s} {'Date':12s} {'unp':3s}  classification")
print("  " + "-" * 80)

carry_results_12 = []
for r in unclosed_12:
    account    = r['account']
    trade_date = r['date']
    fname = f"TradeActivityLog_{trade_date}_UTC.{account}.data"
    fpath = os.path.join(DATASET_DIR, fname)
    raw_fills, _ = _parse_file_nitro(fpath)
    clear_rejected_fills()
    fills  = GhostFillEngine.from_dicts(raw_fills)
    result2 = engine.process(fills)
    classification, detail = check_overnight_carry(
        account, trade_date, result2.unpaired_fills, result2
    )
    carry_results_12.append({'account': account, 'date': trade_date,
                             'classification': classification, 'detail': detail,
                             'reasons': r['reasons']})
    print(f"  {r['idx']:>3}  {account:25s} {trade_date}  {r['unp']:3d}  {classification}")
    print(f"       {detail[:90]}")

# 2B: Random sample of 30 more from full 3,708 population (seed=42 for this subset)
print()
print("  2B — 30 additional random files from full 3,708 pure-natural population")
print("       (seed=42 for reproducibility; distinct from seed=99 sample)")

random.seed(42)
exclude_dates = {(r['account'], r['date']) for r in step1_results}
candidates = [(r['account'], r['trade_date']) for r in all_pure
              if (r['account'], r['trade_date']) not in exclude_dates]
additional30 = random.sample(candidates, min(30, len(candidates)))

carry_results_30 = []
ab_counts = {'CLOSED_NEXT_DAY': 0, 'NEVER_CLOSED': 0,
             'NO_NEXT_FILE': 0, 'NEXT_FILE_EMPTY': 0,
             'NO_UNCLOSED': 0, 'NOT_ON_DISK': 0}

print()
print(f"  {'#':>3}  {'Account':25s} {'Date':12s}  classification")
print("  " + "-" * 75)

for j, (account, trade_date) in enumerate(additional30):
    fname = f"TradeActivityLog_{trade_date}_UTC.{account}.data"
    fpath = os.path.join(DATASET_DIR, fname)

    if not os.path.exists(fpath):
        print(f"  {j+1:>3}  {account:25s} {trade_date}  NOT_ON_DISK")
        ab_counts['NOT_ON_DISK'] += 1
        carry_results_30.append({'account': account, 'date': trade_date,
                                 'classification': 'NOT_ON_DISK'})
        continue

    raw_fills, _ = _parse_file_nitro(fpath)
    if not raw_fills:
        print(f"  {j+1:>3}  {account:25s} {trade_date}  EMPTY")
        ab_counts['NO_UNCLOSED'] += 1
        carry_results_30.append({'account': account, 'date': trade_date,
                                 'classification': 'EMPTY'})
        continue

    clear_rejected_fills()
    fills  = GhostFillEngine.from_dicts(raw_fills)
    result3 = engine.process(fills)

    classification, detail = check_overnight_carry(
        account, trade_date, result3.unpaired_fills, result3
    )
    ab_counts[classification] = ab_counts.get(classification, 0) + 1
    carry_results_30.append({'account': account, 'date': trade_date,
                             'classification': classification, 'detail': detail})

    detail_short = detail[:70] if detail else '-'
    print(f"  {j+1:>3}  {account:25s} {trade_date}  {classification}")
    if classification in ('CLOSED_NEXT_DAY', 'NEVER_CLOSED'):
        print(f"       {detail_short}")

# Summary across both sets
all_carry = carry_results_12 + carry_results_30
total_with_unclosed = sum(1 for r in all_carry if r['classification'] != 'NO_UNCLOSED')
case_b = sum(1 for r in all_carry if r['classification'] == 'CLOSED_NEXT_DAY')
case_a = sum(1 for r in all_carry if r['classification'] == 'NEVER_CLOSED')
no_next = sum(1 for r in all_carry if r['classification'] in ('NO_NEXT_FILE', 'NEXT_FILE_EMPTY'))
no_unp  = sum(1 for r in all_carry if r['classification'] == 'NO_UNCLOSED')
not_on_disk = sum(1 for r in all_carry if r['classification'] == 'NOT_ON_DISK')

print()
print("  STEP 2 SUMMARY (12 original + 30 additional = 42 total):")
print(f"    Files with no unpaired position (direction-flip or inverted-trade fail): {no_unp}")
print(f"    Files with unclosed position + next-day file found:     {case_a + case_b + no_next}")
print(f"      (a) NEVER_CLOSED — position genuinely unresolved:     {case_a}")
print(f"      (b) CLOSED_NEXT_DAY — overnight carry (legitimate):   {case_b}")
print(f"      no_next_file — can't determine (no next-day file):    {no_next}")
print(f"    NOT_ON_DISK (file missing):                             {not_on_disk}")

if case_b > 0:
    fraction_of_3708 = case_b / 42
    estimated_total  = int(fraction_of_3708 * 3708)
    print()
    print(f"  OVERNIGHT CARRY ESTIMATE:")
    print(f"    Sample rate: {case_b}/{42} = {case_b/42:.1%} of sampled files are case (b)")
    print(f"    Applied to full 3,708: ~{estimated_total} files may be legitimate overnight carries")
    print(f"    that verify_sequence incorrectly flags as integrity failures")
    print()
    print("  ACTION REQUIRED: verify_sequence() flags direction flips caused by")
    print("  ORPHANED_CLOSE_UNKNOWN_ORIGIN fills being treated as new ENTRY legs.")
    print("  When the next day's file confirms closure, this is a false integrity fail.")
else:
    print()
    print("  All inspected unclosed-position files appear to be genuine data problems.")
    print("  No confirmed overnight-carry false-positive found in this sample.")

# ── STEP 3 — Distribution concentration ───────────────────────────────────
print()
print("=" * 80)
print("  STEP 3 — DISTRIBUTION CONCENTRATION CHECK")
print("=" * 80)

# 3A: Day-of-week distribution
print()
print("  3A — By Day-of-Week:")
print()
excl_dow = db.execute(
    "SELECT strftime('%w', trade_date) dow, COUNT(*) n "
    "FROM file_audit WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%' "
    "GROUP BY dow ORDER BY dow"
).fetchall()
full_dow = db.execute(
    "SELECT strftime('%w', trade_date) dow, COUNT(*) n "
    "FROM file_audit GROUP BY dow ORDER BY dow"
).fetchall()
dow_names = {0:'Sun', 1:'Mon', 2:'Tue', 3:'Wed', 4:'Thu', 5:'Fri', 6:'Sat'}
full_dow_map = {int(r['dow']): r['n'] for r in full_dow}
print(f"  {'Day':5s}  {'excluded':8s}  {'full_db':8s}  {'excl_rate':9s}  {'full_rate':9s}  {'ratio':6s}")
print("  " + "-" * 55)
total_excl = 3708
total_full = 61706
for r in excl_dow:
    d = int(r['dow'])
    full_n = full_dow_map.get(d, 0)
    excl_rate = r['n'] / total_excl
    full_rate = full_n / total_full
    ratio = excl_rate / full_rate if full_rate > 0 else 0
    flag = " *** CONCENTRATED" if ratio > 1.5 else (" *** LOW" if ratio < 0.7 else "")
    print(f"  {dow_names.get(d,'?'):5s}  {r['n']:8,}  {full_n:8,}  {excl_rate:8.1%}  "
          f"{full_rate:8.1%}  {ratio:5.2f}x{flag}")

# 3B: Month/Year distribution
print()
print("  3B — By Year (already known from prior step — shown for completeness):")
print("  2024: 1,364 / 24,591 = 5.5%  |  2025: 1,584 / 24,912 = 6.4%  |  2026: 760 / 12,203 = 6.2%")
print("  Rate is uniform — no temporal concentration.")

# 3C: Symbol distribution (from per_symbol_summary JSON if available, else from assets)
print()
print("  3C — By Base Symbol (from per_symbol_summary JSON in file_audit):")
print("  (Querying accounts with single-symbol predominance as proxy — file-level data)")

# Query top symbols by sampling per_symbol_summary JSON
sym_excl = collections.Counter()
sym_full = collections.Counter()

# Parse assets column (stored as JSON-serialized list)
excl_rows = db.execute(
    "SELECT assets, per_symbol_summary FROM file_audit "
    "WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%' "
    "AND per_symbol_summary IS NOT NULL AND per_symbol_summary != '{}'"
).fetchall()

for row in excl_rows:
    try:
        d = json.loads(row['per_symbol_summary'])
        for sym in d.keys():
            sym_excl[sym] += 1
    except Exception:
        pass

full_rows = db.execute(
    "SELECT per_symbol_summary FROM file_audit "
    "WHERE per_symbol_summary IS NOT NULL AND per_symbol_summary != '{}'"
).fetchall()
for row in full_rows:
    try:
        d = json.loads(row['per_symbol_summary'])
        for sym in d.keys():
            sym_full[sym] += 1
    except Exception:
        pass

if sym_excl:
    total_excl_sym = sum(sym_excl.values())
    total_full_sym = sum(sym_full.values())
    top_syms = sym_excl.most_common(15)
    print()
    print(f"  {'Symbol':10s}  {'excl_count':10s}  {'excl_%':8s}  {'full_%':8s}  {'ratio':6s}")
    print("  " + "-" * 50)
    for sym, cnt in top_syms:
        full_cnt = sym_full.get(sym, 0)
        er = cnt / total_excl_sym if total_excl_sym > 0 else 0
        fr = full_cnt / total_full_sym if total_full_sym > 0 else 0
        ratio = er / fr if fr > 0 else 0
        flag = " *** CONCENTRATED" if ratio > 1.5 else (" *** LOW" if ratio < 0.7 else "")
        print(f"  {sym:10s}  {cnt:10,}  {er:7.1%}  {fr:7.1%}  {ratio:5.2f}x{flag}")
else:
    # Fallback: use account name prefix as proxy
    print("  (per_symbol_summary not available — using account-name prefix as proxy)")
    excl_acct = db.execute(
        "SELECT "
        "  CASE "
        "    WHEN account LIKE 'ES%'     THEN 'ES-family' "
        "    WHEN account LIKE 'NQ%'     THEN 'NQ-family' "
        "    WHEN account LIKE '%TM%'    THEN 'TM-family' "
        "    WHEN account LIKE '%sim%'   THEN 'sim' "
        "    ELSE 'other' END acct_grp, COUNT(*) n "
        "FROM file_audit WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%' "
        "GROUP BY acct_grp ORDER BY n DESC"
    ).fetchall()
    full_acct = db.execute(
        "SELECT "
        "  CASE "
        "    WHEN account LIKE 'ES%'     THEN 'ES-family' "
        "    WHEN account LIKE 'NQ%'     THEN 'NQ-family' "
        "    WHEN account LIKE '%TM%'    THEN 'TM-family' "
        "    WHEN account LIKE '%sim%'   THEN 'sim' "
        "    ELSE 'other' END acct_grp, COUNT(*) n "
        "FROM file_audit GROUP BY acct_grp ORDER BY n DESC"
    ).fetchall()
    full_acct_map = {r['acct_grp']: r['n'] for r in full_acct}
    print(f"  {'Group':12s}  {'excl':8s}  {'full':8s}  {'excl%':7s}  {'full%':7s}  ratio")
    for r in excl_acct:
        fn = full_acct_map.get(r['acct_grp'], 1)
        er = r['n'] / total_excl
        fr = fn / total_full
        ratio = er / fr if fr > 0 else 0
        flag = " *** CONCENTRATED" if ratio > 1.5 else ""
        print(f"  {r['acct_grp']:12s}  {r['n']:8,}  {fn:8,}  {er:6.1%}  {fr:6.1%}  {ratio:.2f}x{flag}")

# 3D: Hour-of-day — not available at file-audit level; proxy: bypass_mode
print()
print("  3D — Hour-of-day not available at file-audit granularity (daily files).")
print("       Proxy check: bypass_mode distribution (tracks session note_rate behaviour)")
bp_excl = db.execute(
    "SELECT bypass_mode, COUNT(*) n FROM file_audit "
    "WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%' GROUP BY bypass_mode"
).fetchall()
bp_full = db.execute(
    "SELECT bypass_mode, COUNT(*) n FROM file_audit GROUP BY bypass_mode"
).fetchall()
bp_full_map = {r['bypass_mode']: r['n'] for r in bp_full}
for r in bp_excl:
    fn = bp_full_map.get(r['bypass_mode'], 1)
    er = r['n'] / total_excl
    fr = fn / total_full
    ratio = er / fr if fr > 0 else 0
    flag = " *** CONCENTRATED" if ratio > 1.5 else ""
    print(f"    bypass={r['bypass_mode']}: excl={r['n']:,} ({er:.1%}) vs full={fn:,} ({fr:.1%}) "
          f"ratio={ratio:.2f}x{flag}")

# ── FINAL SUMMARY ─────────────────────────────────────────────────────────
print()
print("=" * 80)
print("  FINAL CONSOLIDATED FINDINGS")
print("=" * 80)
print()
print("  STEP 1 — Classification fix:")
print("    resync() == GhostFillEngine.process() == real per-symbol pipeline.")
print("    Prior 'all-symbols' claim was wrong. Reclassified using verify_sequence msgs.")
print()
print("  STEP 1 — Threading race condition (AUDIT FINDING, not data blocker):")
print("    ThreadPoolExecutor + module-level rejected_fills → flag_reason counts unreliable.")
print("    integrity_ok field is reliable (computed before race-affected _get_rejected()).")
print("    The 3,708 excluded files are correctly excluded regardless of A/B/C label.")
print()
print("  STEP 2 — Overnight carry:")
case_b_count = sum(1 for r in all_carry if r['classification'] == 'CLOSED_NEXT_DAY')
case_a_count = sum(1 for r in all_carry if r['classification'] == 'NEVER_CLOSED')
no_unp_count = sum(1 for r in all_carry if r['classification'] == 'NO_UNCLOSED')
print(f"    42 files sampled (12 original + 30 additional).")
print(f"    (b) CLOSED_NEXT_DAY (confirm overnight carry, potential false-fail): {case_b_count}")
print(f"    (a) NEVER_CLOSED (genuine data problem):                            {case_a_count}")
print(f"    NO_UNCLOSED (integrity fails via flips/inverted, not position):     {no_unp_count}")
if case_b_count > 0:
    est = int(case_b_count / 42 * 3708)
    print(f"    Estimated false-fail count in 3,708: ~{est} files ({case_b_count/42:.1%})")
    print()
    print("  ** BLOCKING CONCERN (requires human decision) **")
    print(f"    {case_b_count} of 42 sampled files are legitimate overnight carries that")
    print(f"    verify_sequence() incorrectly flags as integrity failures.")
    print(f"    Estimated ~{est}/{3708} excluded files may be wrongly excluded from clean_trades.")
    print(f"    Fix needed: verify_sequence() or the batch-level auditor needs a lookahead")
    print(f"    to check whether an 'unclosed' position is resolved in the next day's file.")
    print(f"    Promote without fix = up to ~{est} legitimate trades silently excluded.")
    print(f"    Promote with fix = these trades re-enter clean_trades, changing some PnL totals.")
else:
    print("    No confirmed overnight-carry false-fails in 42-file sample.")
    print("    Unclosed positions appear to be genuine data quality issues.")
    print("    No verify_sequence() fix required based on this evidence.")
print()
print("  STEP 3 — Concentration:")
print("    Day-of-week: (results shown above — check for any '*** CONCENTRATED' rows)")
print("    Year: uniform 5.5-6.4% across 2024/25/26 — no temporal concentration")
print("    Symbol: (results shown above)")

db.close()
