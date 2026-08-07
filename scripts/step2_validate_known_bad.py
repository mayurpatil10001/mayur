"""
Step 2 — Prove the Fix Works on Known-Bad Cases
================================================
Tests the GFRE v3 bounds fix against five known-bad account/date combos:
  1. TS_5    (all dates)
  2. TS_6    (all dates)
  3. IPS_TM_11 (all dates)
  4. TM_2    (all dates)
  5. T-S_production 2023-09-06

For each file reports:
  - New PnL numbers (dirty and clean)
  - Count and sample of rejected_fills
  - verify_sequence() position-balance result
  - Whether any implausible trade remains (> $2M)
"""
import sys, os, glob, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, _base_symbol,
    pair_fills_to_trades,
    get_rejected_fills, clear_rejected_fills,
    MAX_SANE_QUANTITY,
)
import collections as _col

ABSOLUTE_TRADE_PNL_CEILING = 2_000_000.0   # same value as in ghost_fill_cleaner

DATASET = 'dataset'
DATE_RE = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')

# Known-bad target accounts (and one specific date)
TARGET_ACCOUNTS = {'TS_5', 'TS_6', 'IPS_TM_11', 'TM_2', 'T-S_production'}
SPECIFIC_DATE   = ('T-S_production', '2023-09-06')

SEP = '=' * 72

print(SEP)
print('  STEP 2 — KNOWN-BAD CASE VALIDATION  (GFRE v3 bounds fix)')
print(SEP)
print('  MAX_SANE_QUANTITY     :', MAX_SANE_QUANTITY)
print('  ABSOLUTE_TRADE_CEIL   : ${:,.0f}'.format(ABSOLUTE_TRADE_PNL_CEILING))
print()

# Gather files
all_files = glob.glob(os.path.join(DATASET, '*.data'))
target_files = []
for fp in sorted(all_files):
    fname = os.path.basename(fp)
    m = DATE_RE.match(fname)
    if not m:
        continue
    date_str, acct = m.group(1), m.group(2)
    if acct in TARGET_ACCOUNTS:
        target_files.append((acct, date_str, fp, fname))

print('  Files to process: {:,}  (across {} target accounts)'.format(
    len(target_files), len(TARGET_ACCOUNTS)))
print()

# Per-account summary accumulators
acct_summary = {}

pass_count = fail_count = skip_count = 0
total_rejected = 0

for acct, date_str, fp, fname in target_files:
    if acct not in acct_summary:
        acct_summary[acct] = {
            'files': 0, 'raw': 0, 'rejected': 0,
            'dirty_net': 0.0, 'clean_net': 0.0,
            'impossible_trades': 0, 'impossible_files': 0,
            'int_fail': 0,
        }

    clear_rejected_fills()

    try:
        raw, _ = _parse_file_nitro(fp)
    except Exception as e:
        print('  ERROR  ' + fname + '  parse failed: ' + str(e))
        skip_count += 1
        continue

    if not raw:
        acct_summary[acct]['files'] += 1
        continue

    # Convert — is_valid() now enforces bounds, rejected_fills populated
    fills = GhostFillEngine.from_dicts(raw)
    rejected = get_rejected_fills()
    n_raw = len(fills)
    n_rejected = len(rejected)
    total_rejected += n_rejected

    # Dirty run — per-symbol FIFO, no ghost filter (matches patched cleaner)
    dirty_sym = _col.defaultdict(list)
    for f in list(fills):
        f.suggests_ghost = False
        dirty_sym[f.base_symbol].append(f)
    dirty_net = 0.0
    for _bs, _sf in dirty_sym.items():
        _sf_s = sorted(_sf, key=lambda _f: (_f.ts_val, _f.position_order))
        _dt, _ = pair_fills_to_trades(_sf_s)
        dirty_net += sum(_t.pnl_dollars for _t in _dt)

    # Clean run — full per-symbol engine (v3)
    fills2         = GhostFillEngine.from_dicts(raw)
    _engine        = GhostFillEngine()
    _clean_result  = _engine.process(fills2)
    c_trades       = _clean_result.trades
    c_unpaired     = _clean_result.unpaired_fills
    clean_net      = sum(_t.pnl_dollars for _t in c_trades)
    int_ok         = _clean_result.integrity_ok
    int_msgs       = _clean_result.notes[-4:]
    flips          = _clean_result.direction_flips

    # Absolute ceiling check
    worst_trade = max((abs(t.pnl_dollars) for t in c_trades), default=0.0)
    impossible_trade = worst_trade > ABSOLUTE_TRADE_PNL_CEILING
    impossible_file  = abs(clean_net) > 10_000_000.0

    # Update summary
    s = acct_summary[acct]
    s['files']      += 1
    s['raw']        += n_raw
    s['rejected']   += n_rejected
    s['dirty_net']  += dirty_net
    s['clean_net']  += clean_net
    if impossible_trade:
        s['impossible_trades'] += 1
    if impossible_file:
        s['impossible_files'] += 1
    if not int_ok:
        s['int_fail'] += 1

    # Print details for files with issues or the specific date
    is_specific = (acct == SPECIFIC_DATE[0] and date_str == SPECIFIC_DATE[1])
    has_issue   = impossible_trade or impossible_file or n_rejected > 0 or not int_ok

    if has_issue or is_specific:
        status = 'PASS' if (not impossible_trade and not impossible_file) else 'FAIL'
        print('  [' + status + ']  ' + fname)
        print('        raw=' + str(n_raw) +
              '  ghosts=' + str(_clean_result.ghost_fills_dropped) +
              '  clean_trades=' + str(len(c_trades)) +
              '  rejected_fills=' + str(n_rejected))
        print('        dirty_net={:>20,.2f}'.format(dirty_net))
        print('        clean_net={:>20,.2f}'.format(clean_net))
        print('        worst_trade_pnl={:>16,.2f}  {}'.format(
            worst_trade, '!!! STILL IMPOSSIBLE !!!' if impossible_trade else 'OK'))
        print('        integrity={}'.format('PASS' if int_ok else 'FAIL: ' + '; '.join(int_msgs[:2])))

        if n_rejected > 0:
            print('        Sample rejected fills (first 5):')
            for r in rejected[:5]:
                print('          sym={} side={} price={} qty={} field={} actual={} bound={} reason={}'.format(
                    r.get('symbol', ''), r.get('side', ''),
                    r.get('price', ''), r.get('quantity', ''),
                    r.get('field', ''), r.get('actual_value', ''),
                    r.get('bound', ''), r.get('reason', '')))
        print()

        if status == 'FAIL':
            fail_count += 1
        else:
            pass_count += 1
    else:
        pass_count += 1

print()
print(SEP)
print('  PER-ACCOUNT SUMMARY')
print(SEP)
print('  {:20s} {:>6} {:>8} {:>8} {:>14} {:>14} {:>9} {:>9} {:>8}'.format(
    'Account', 'Files', 'Raw', 'Reject', 'DirtyNet', 'CleanNet', 'ImpTrd', 'ImpFile', 'IntFail'))
print('  ' + '-' * 100)
for acct2, s in sorted(acct_summary.items()):
    print('  {:20s} {:>6} {:>8,} {:>8,} {:>14,.0f} {:>14,.0f} {:>9} {:>9} {:>8}'.format(
        acct2, s['files'], s['raw'], s['rejected'],
        s['dirty_net'], s['clean_net'],
        s['impossible_trades'], s['impossible_files'], s['int_fail']))

print()
print(SEP)
print('  VERDICT')
print(SEP)
all_impossible = sum(s['impossible_trades'] + s['impossible_files']
                     for s in acct_summary.values())
all_int_fail   = sum(s['int_fail'] for s in acct_summary.values())

print('  Total files processed   : {:,}'.format(sum(s['files'] for s in acct_summary.values())))
print('  Total fills rejected    : {:,}  (by new bounds check)'.format(total_rejected))
print('  Files with impossible PnL remaining: {:,}'.format(all_impossible))
print('  Files with integrity failure        : {:,}'.format(all_int_fail))
print()
if all_impossible == 0:
    print('  BOUNDS FIX WORKS: zero impossible PnL values remain in test accounts.')
    print('  Integrity failures shown above require manual review (expected for')
    print('  files where corrupted fills were mid-sequence).')
else:
    print('  *** STOP: ' + str(all_impossible) + ' impossible value(s) remain after fix.')
    print('  *** Do NOT proceed to full re-run. Investigate cases above first.')
print(SEP)
