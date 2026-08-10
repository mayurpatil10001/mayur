"""
scripts/step_final_checks_p2.py
================================
Steps 2+3 of the "Final Two Checks Before Promotion" task.
Fixed: replaced Unicode arrows with ASCII '->' to avoid cp1252 encoding errors.
Uses same seed=99 sample for the 25-file base + 30 additional for overnight check.
"""
import os, sys, json, random, collections, datetime, re

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

import sqlite3
DATASET_DIR = os.path.join(PROJECT_ROOT, 'dataset')
DB          = os.path.join(PROJECT_ROOT, 'trading_platform_clean_v2.db')

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, clear_rejected_fills, get_rejected_fills
)

engine = GhostFillEngine()

# Same 25 files (seed=99)
random.seed(99)
all_pure = db.execute(
    "SELECT account, trade_date FROM file_audit WHERE integrity_ok=0 "
    "AND flag_reason NOT LIKE '%rejected_fills%' ORDER BY account, trade_date"
).fetchall()
sample25 = random.sample(list(all_pure), 25)
sample25_set = {(r['account'], r['trade_date']) for r in sample25}

# ── Helpers ──────────────────────────────────────────────────────────────

def get_next_day_file(account, trade_date_str):
    d = datetime.datetime.strptime(trade_date_str, '%Y-%m-%d').date()
    for offset in [1, 2, 3, 4, 5]:
        nd = d + datetime.timedelta(days=offset)
        nd_str = nd.strftime('%Y-%m-%d')
        fname = f"TradeActivityLog_{nd_str}_UTC.{account}.data"
        fpath = os.path.join(DATASET_DIR, fname)
        if os.path.exists(fpath):
            return fpath, nd_str
    return None, None

def run_engine(fpath):
    raw_fills, _ = _parse_file_nitro(fpath)
    if not raw_fills:
        return None, []
    clear_rejected_fills()
    fills  = GhostFillEngine.from_dicts(raw_fills)
    result = engine.process(fills)
    rejected = get_rejected_fills()
    return result, rejected

def base_sym_of(sym):
    return re.sub(r'[FGHJKMNQUVXZ]\d+$', '', sym)

def check_overnight_carry(account, trade_date, result):
    """
    Returns: (classification_str, detail_str)
      'NO_UNCLOSED'      -- no unpaired fills
      'CLOSED_NEXT_DAY'  -- next day's file has a closing fill (case b)
      'NEVER_CLOSED'     -- next day's file found but no closing fill (case a)
      'NO_NEXT_FILE'     -- no next-day file on disk
      'NEXT_FILE_EMPTY'  -- next-day file empty
    """
    if not result.unpaired_fills:
        return 'NO_UNCLOSED', 'no unpaired position'

    # Net position by base_symbol
    unclosed = {}
    for f in result.unpaired_fills:
        bs = base_sym_of(f.base_symbol)
        delta = f.quantity if f.side == 'BUY' else -f.quantity
        unclosed[bs] = unclosed.get(bs, 0) + delta

    next_path, next_date = get_next_day_file(account, trade_date)
    if not next_path:
        return 'NO_NEXT_FILE', f"unclosed={unclosed}"

    raw2, _ = _parse_file_nitro(next_path)
    if not raw2:
        return 'NEXT_FILE_EMPTY', f"unclosed={unclosed}, next={next_date}"

    # Look for a fill in next day's file that closes one of the unclosed positions
    closing_found = {}
    for fd in raw2:
        sym = fd.get('base_symbol') or fd.get('symbol', '')
        bs  = base_sym_of(sym)
        if bs not in unclosed:
            continue
        delta = unclosed[bs]
        side  = fd.get('side', '')
        qty   = fd.get('quantity', 0)
        ts    = fd.get('timestamp', '')
        oc    = fd.get('open_close', '')
        # Closing fill: opposite direction to the open position
        if (delta > 0 and side == 'SELL') or (delta < 0 and side == 'BUY'):
            if bs not in closing_found:
                closing_found[bs] = f"{side} {qty} {sym} ts={ts[:19]} oc={oc} on {next_date}"

    if closing_found:
        detail = '; '.join([f"{s}:{v}" for s, v in closing_found.items()])
        return 'CLOSED_NEXT_DAY', f"unclosed={unclosed} -> {detail}"
    else:
        return 'NEVER_CLOSED', f"unclosed={unclosed}, no match in {next_date}"

# ── STEP 2A — 25-file sample: check files with unpaired fills ─────────────
print("=" * 80)
print("  STEP 2A -- OVERNIGHT CARRY CHECK (25-file sample with unpaired fills)")
print("=" * 80)
print()

carry_all = []
files_with_unpaired = []

for row in sample25:
    account    = row['account']
    trade_date = row['trade_date']
    fname = f"TradeActivityLog_{trade_date}_UTC.{account}.data"
    fpath = os.path.join(DATASET_DIR, fname)
    if not os.path.exists(fpath):
        continue
    result, _ = run_engine(fpath)
    if result is None:
        continue
    if result.unpaired_fills:
        files_with_unpaired.append((account, trade_date, result))

print(f"  Files with unpaired fills from 25-file sample: {len(files_with_unpaired)}")
print()
print(f"  {'Account':25s} {'Date':12s} {'unp':3s}  classification + detail")
print("  " + "-" * 90)

for (account, trade_date, result) in files_with_unpaired:
    classification, detail = check_overnight_carry(account, trade_date, result)
    carry_all.append({'account': account, 'date': trade_date,
                     'classification': classification, 'detail': detail})
    # ASCII-safe print
    safe_detail = detail.replace('\u2192', '->').encode('ascii', errors='replace').decode()
    print(f"  {account:25s} {trade_date}  {len(result.unpaired_fills):3d}  {classification}")
    print(f"    {safe_detail[:90]}")

# ── STEP 2B — 30 additional random files ──────────────────────────────────
print()
print("=" * 80)
print("  STEP 2B -- 30 ADDITIONAL RANDOM FILES (seed=42)")
print("=" * 80)
print()

random.seed(42)
candidates_all = [(r['account'], r['trade_date']) for r in all_pure
                  if (r['account'], r['trade_date']) not in sample25_set]
additional30 = random.sample(candidates_all, min(30, len(candidates_all)))

print(f"  {'#':>3}  {'Account':25s} {'Date':12s} {'unp':3s}  classification")
print("  " + "-" * 80)

for j, (account, trade_date) in enumerate(additional30):
    fname = f"TradeActivityLog_{trade_date}_UTC.{account}.data"
    fpath = os.path.join(DATASET_DIR, fname)
    if not os.path.exists(fpath):
        print(f"  {j+1:>3}  {account:25s} {trade_date}  ---  NOT_ON_DISK")
        carry_all.append({'account': account, 'date': trade_date,
                         'classification': 'NOT_ON_DISK'})
        continue

    result, _ = run_engine(fpath)
    if result is None:
        print(f"  {j+1:>3}  {account:25s} {trade_date}  ---  EMPTY")
        carry_all.append({'account': account, 'date': trade_date,
                         'classification': 'EMPTY'})
        continue

    classification, detail = check_overnight_carry(account, trade_date, result)
    carry_all.append({'account': account, 'date': trade_date,
                     'classification': classification, 'detail': detail})
    safe_detail = detail.replace('\u2192', '->').encode('ascii', errors='replace').decode()
    print(f"  {j+1:>3}  {account:25s} {trade_date}  {len(result.unpaired_fills):3d}  {classification}")
    if classification in ('CLOSED_NEXT_DAY', 'NEVER_CLOSED'):
        print(f"       {safe_detail[:85]}")

# ── STEP 2 SUMMARY ────────────────────────────────────────────────────────
print()
print("=" * 80)
print("  STEP 2 SUMMARY")
print("=" * 80)

from collections import Counter
class_counts = Counter(r['classification'] for r in carry_all)
total_samples = len(carry_all)
no_unclosed   = class_counts['NO_UNCLOSED']
case_b        = class_counts['CLOSED_NEXT_DAY']
case_a        = class_counts['NEVER_CLOSED']
no_next       = class_counts['NO_NEXT_FILE'] + class_counts['NEXT_FILE_EMPTY']

inspected = total_samples - class_counts['NOT_ON_DISK'] - class_counts['EMPTY']
files_with_unp = case_a + case_b + no_next

print()
print(f"  Total records in carry check: {total_samples}")
print(f"  Files inspected (on disk, not empty): {inspected}")
print(f"  NO_UNCLOSED (fail is flip or inverted, no open position): {no_unclosed}")
print(f"  Files with unclosed position: {files_with_unp}")
print(f"    (a) NEVER_CLOSED (genuine unresolved data problem):    {case_a}")
print(f"    (b) CLOSED_NEXT_DAY (legitimate overnight carry):      {case_b}")
print(f"    NO_NEXT_FILE or NEXT_FILE_EMPTY (inconclusive):        {no_next}")

if case_b > 0:
    rate = case_b / max(inspected, 1)
    est  = int(rate * 3708)
    print()
    print(f"  ** OVERNIGHT CARRY FINDING (BLOCKING CONCERN) **")
    print(f"  {case_b}/{inspected} inspected files are legitimate overnight carries that")
    print(f"  verify_sequence() incorrectly flags as integrity failures.")
    print(f"  Extrapolated to full 3,708: estimated ~{est} files (~{rate:.1%}) affected.")
    print(f"  These are excluded from clean_trades but should NOT be.")
else:
    print()
    print("  No confirmed overnight-carry false-fails in sample.")

# ── STEP 3 — Distribution concentration ───────────────────────────────────
print()
print("=" * 80)
print("  STEP 3 -- DISTRIBUTION CONCENTRATION CHECK")
print("=" * 80)

total_excl = 3708
total_full = 61706

# 3A: Day of week
print()
print("  3A -- Day-of-Week distribution:")
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
print(f"  {'Day':5s}  {'excl':6s}  {'full':7s}  {'excl%':7s}  {'full%':7s}  {'ratio':6s}  concentration?")
print("  " + "-" * 65)
for r in excl_dow:
    d = int(r['dow'])
    fn = full_dow_map.get(d, 0)
    er = r['n'] / total_excl
    fr = fn / total_full
    ratio = er / fr if fr > 0 else 0
    flag = "*** HIGH" if ratio > 1.5 else ("LOW" if ratio < 0.7 else "proportional")
    print(f"  {dow_names.get(d,'?'):5s}  {r['n']:6,}  {fn:7,}  {er:6.1%}  {fr:6.1%}  {ratio:5.2f}x  {flag}")

# 3B: Symbol (from per_symbol_summary JSON)
print()
print("  3B -- By Base Symbol (from per_symbol_summary JSON):")
sym_excl = Counter()
sym_full = Counter()

excl_rows = db.execute(
    "SELECT per_symbol_summary FROM file_audit "
    "WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%' "
    "AND per_symbol_summary IS NOT NULL"
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
    "WHERE per_symbol_summary IS NOT NULL"
).fetchall()
for row in full_rows:
    try:
        d = json.loads(row['per_symbol_summary'])
        for sym in d.keys():
            sym_full[sym] += 1
    except Exception:
        pass

te_sym = sum(sym_excl.values())
tf_sym = sum(sym_full.values())

if sym_excl:
    print(f"  {'Symbol':8s}  {'excl':6s}  {'full':7s}  {'excl%':7s}  {'full%':7s}  {'ratio':6s}  concentration?")
    print("  " + "-" * 70)
    for sym, cnt in sym_excl.most_common(15):
        fn = sym_full.get(sym, 0)
        er = cnt / te_sym if te_sym > 0 else 0
        fr = fn / tf_sym  if tf_sym > 0 else 0
        ratio = er / fr if fr > 0 else 0
        flag = "*** HIGH" if ratio > 1.5 else ("LOW" if ratio < 0.7 else "proportional")
        print(f"  {sym:8s}  {cnt:6,}  {fn:7,}  {er:6.1%}  {fr:6.1%}  {ratio:5.2f}x  {flag}")
else:
    print("  per_symbol_summary not populated -- using account-name proxy")
    acct_grps_q = """
    SELECT
      CASE WHEN account LIKE 'ES%'  THEN 'ES' WHEN account LIKE 'NQ%' THEN 'NQ'
           WHEN account LIKE '%TM%' THEN 'TM' WHEN account LIKE '%sim%' THEN 'sim'
           ELSE 'other' END grp, COUNT(*) n
    FROM file_audit {where}
    GROUP BY grp ORDER BY n DESC"""
    excl_acct = db.execute(acct_grps_q.format(where="WHERE integrity_ok=0 AND flag_reason NOT LIKE '%rejected_fills%'")).fetchall()
    full_acct = db.execute(acct_grps_q.format(where="")).fetchall()
    full_acct_map = {r['grp']: r['n'] for r in full_acct}
    for r in excl_acct:
        fn = full_acct_map.get(r['grp'], 1)
        er = r['n'] / total_excl
        fr = fn / total_full
        ratio = er / fr if fr > 0 else 0
        flag = "*** HIGH" if ratio > 1.5 else ("LOW" if ratio < 0.7 else "proportional")
        print(f"  {r['grp']:8s}  {r['n']:6,}  {fn:7,}  {er:6.1%}  {fr:6.1%}  {ratio:.2f}x  {flag}")

# 3C: bypass_mode proxy (no hour-of-day available)
print()
print("  3C -- bypass_mode (proxy for session note-rate behaviour):")
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
    flag = "*** HIGH" if ratio > 1.5 else ("LOW" if ratio < 0.7 else "proportional")
    print(f"  bypass={r['bypass_mode']}: excl={r['n']:,} ({er:.1%}) full={fn:,} ({fr:.1%}) ratio={ratio:.2f}x  {flag}")

# ── STEP 3 SUMMARY ─────────────────────────────────────────────────────
print()
print("  STEP 3 SUMMARY:")
print("  Check all ratios above. If any 'HIGH' row found, concentration is confirmed.")
print("  Year distribution already confirmed proportional (5.5-6.4% all years).")

db.close()
print()
print("=" * 80)
print("  DONE")
print("=" * 80)
