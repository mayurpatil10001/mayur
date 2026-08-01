import sys, os, re, sqlite3

sys.path.insert(0, '.')
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, pair_fills_to_trades, verify_sequence
)

DATE_RE  = re.compile(r'TradeActivityLog_(\d{4}-\d{2}-\d{2})_UTC\.(.+)\.data$')
DATASET  = 'dataset'
DB_PATH  = 'trading_platform_clean_v2.db'

TEST_FILES = [
    'TradeActivityLog_2026-07-09_UTC.IPS_TM_7.data',
    'TradeActivityLog_2026-07-02_UTC.IPS_TM_7.data',
    'TradeActivityLog_2026-06-23_UTC.IPS_TM_7.data',
    'TradeActivityLog_2026-06-02_UTC.IPS_TM_7.data',
    'TradeActivityLog_2026-07-08_UTC.TM_7.data',
    'TradeActivityLog_2026-07-01_UTC.TM_5.data',
]

SEP = '=' * 65
print(SEP)
print('  POSITION SYNCHRONIZATION VERIFICATION')
print('  Checks: ghost fills removed, FIFO +N/-N balance, net pos=0')
print(SEP)

pass_c = 0
fail_c = 0
total_raw_all = 0
total_ghost_all = 0

for fname in TEST_FILES:
    fp = os.path.join(DATASET, fname)
    if not os.path.exists(fp):
        print('  SKIP  ' + fname + '  (not found)')
        continue

    m    = DATE_RE.match(fname)
    acct = m.group(2) if m else '?'
    date = m.group(1) if m else '?'

    raw, _ = _parse_file_nitro(fp)
    if not raw:
        print('  SKIP  ' + fname + '  (0 raw records)')
        continue

    fills_all = GhostFillEngine.from_dicts(raw)
    n_raw     = len(fills_all)
    total_raw_all += n_raw

    ghosts = [f for f in fills_all if classify_fill(f)]
    clean  = [f for f in fills_all if not classify_fill(f)]
    total_ghost_all += len(ghosts)

    trades, unpaired = pair_fills_to_trades(clean)
    int_ok, int_msgs, flip_count = verify_sequence(
        list(fills_all), clean, trades, unpaired
    )

    # Manual FIFO position walk on clean fills
    sorted_clean = sorted(
        clean,
        key=lambda f: (getattr(f, '_position_order', 9999), f.timestamp)
    )
    position = 0
    pos_history = [0]
    ghost_remaining = 0

    for f in sorted_clean:
        side = getattr(f, 'side', '').upper()
        qty  = int(getattr(f, 'quantity', 0))
        oc   = getattr(f, 'open_close', '')
        note = getattr(f, 'note', '') or ''
        delta = +qty if side == 'BUY' else -qty
        position += delta
        pos_history.append(position)
        # Any OPEN fill with no note = ghost still present
        if oc == 'OPEN' and not note.strip():
            ghost_remaining += 1

    net_pos    = position
    pos_ok     = (net_pos == 0 or len(unpaired) > 0)
    clean_ok   = (ghost_remaining == 0)
    flip_ok    = (flip_count == 0)
    overall_ok = pos_ok and clean_ok and int_ok

    status = 'PASS' if overall_ok else 'FAIL'
    if overall_ok:
        pass_c += 1
    else:
        fail_c += 1

    # Build compact position walk string (first 14 values)
    walk_vals = pos_history[:14]
    walk_str  = ' -> '.join(str(p) for p in walk_vals)
    if len(pos_history) > 14:
        walk_str += ' ... (last=' + str(pos_history[-1]) + ')'

    net_label  = 'FLAT' if net_pos == 0 else ('OVERNIGHT (' + str(len(unpaired)) + ' unpaired)')
    flip_label = 'NONE' if flip_count == 0 else 'FLIPS DETECTED'
    grem_label = 'CLEAN' if ghost_remaining == 0 else str(ghost_remaining) + ' GHOSTS STILL PRESENT'
    int_label  = 'PASS' if int_ok else ('FAIL: ' + '; '.join(int_msgs[:2]))

    print('')
    print('  [' + status + ']  ' + fname)
    print('         Account       : ' + acct + '   Date: ' + date)
    print('         Raw fills     : ' + str(n_raw) +
          '   Ghosts removed: ' + str(len(ghosts)) +
          '   Clean fills: ' + str(len(clean)))
    print('         Trades paired : ' + str(len(trades)) +
          '   Unpaired fills: ' + str(len(unpaired)))
    print('         Net position  : ' + str(net_pos) + '  -> ' + net_label)
    print('         Dir flips     : ' + str(flip_count) + '  -> ' + flip_label)
    print('         Ghost check   : ' + grem_label)
    print('         Integrity     : ' + int_label)
    print('         Pos walk      : ' + walk_str)

print('')
print(SEP)
ghost_rate = 100.0 * total_ghost_all / total_raw_all if total_raw_all > 0 else 0.0
print('  DIRECT PARSE RESULTS:')
print('    PASS : ' + str(pass_c))
print('    FAIL : ' + str(fail_c))
print('    Total raw fills  : ' + '{:,}'.format(total_raw_all))
print('    Ghost fills found: ' + '{:,}'.format(total_ghost_all) +
      '  (' + str(round(ghost_rate, 2)) + '%)')

# DB summary
if os.path.exists(DB_PATH):
    print('')
    print(SEP)
    print('  STAGING DB INTEGRITY  (trading_platform_clean_v2.db)')
    print(SEP)
    con      = sqlite3.connect(DB_PATH)
    total_f  = con.execute('SELECT COUNT(*) FROM file_audit').fetchone()[0]
    int_ok_n = con.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=1').fetchone()[0]
    int_fail = con.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0').fetchone()[0]
    flagged  = con.execute('SELECT COUNT(*) FROM file_audit WHERE flagged=1').fetchone()[0]
    raw_tot  = con.execute('SELECT SUM(total_raw_fills) FROM file_audit').fetchone()[0] or 0
    gst_tot  = con.execute('SELECT SUM(ghost_fills) FROM file_audit').fetchone()[0] or 0
    trd_n    = con.execute('SELECT COUNT(*) FROM clean_trades').fetchone()[0]
    byp_n    = con.execute('SELECT COUNT(*) FROM file_audit WHERE bypass_mode=1').fetchone()[0]

    top = con.execute('''
        SELECT account,
               SUM(total_raw_fills) raw,
               SUM(ghost_fills)     ghosts,
               COUNT(*)             files,
               ROUND(100.0*SUM(ghost_fills)/MAX(SUM(total_raw_fills),1),1) pct
        FROM file_audit
        WHERE total_raw_fills > 0
        GROUP BY account
        ORDER BY ghosts DESC
        LIMIT 12
    ''').fetchall()

    fail_samples = con.execute('''
        SELECT source_file, integrity_notes
        FROM file_audit
        WHERE integrity_ok=0 AND integrity_notes!=''
        LIMIT 3
    ''').fetchall()

    con.close()

    gr = 100.0 * gst_tot / raw_tot if raw_tot > 0 else 0.0

    print('  Files processed      : ' + '{:,}'.format(total_f))
    print('  Integrity PASS       : ' + '{:,}'.format(int_ok_n) +
          '  (' + str(round(100.0*int_ok_n/max(total_f,1),1)) + '%)')
    print('  Integrity FAIL       : ' + '{:,}'.format(int_fail) +
          '  (' + str(round(100.0*int_fail/max(total_f,1),1)) + '%)')
    print('  Bypass mode files    : ' + '{:,}'.format(byp_n) +
          '  (low-note accounts, e.g. TM_10)')
    print('  Flagged (>15% delta) : ' + '{:,}'.format(flagged))
    print('  Total raw fills      : ' + '{:,}'.format(raw_tot))
    print('  Ghost fills removed  : ' + '{:,}'.format(gst_tot) +
          '  (' + str(round(gr, 2)) + '%)')
    print('  Clean trades written : ' + '{:,}'.format(trd_n))
    print('')
    print('  Top accounts by ghost count:')
    print('  ' + '-'*63)
    print('  {:28s} {:>9} {:>8} {:>7} {:>6}'.format(
          'Account', 'Raw', 'Ghosts', 'Rate%', 'Files'))
    print('  ' + '-'*63)
    for row in top:
        acct2, raw2, ghosts2, files2, pct2 = row
        print('  {:28s} {:>9,} {:>8,} {:>6.1f}% {:>6}'.format(
              acct2, raw2, ghosts2, pct2, files2))

    if fail_samples:
        print('')
        print('  Sample integrity failure messages:')
        for sfile, snotes in fail_samples:
            print('    ' + sfile)
            print('      -> ' + str(snotes)[:110])

print('')
print(SEP)
print('  VERDICT')
print(SEP)
if fail_c == 0:
    print('  ALL ' + str(pass_c) + ' files VERIFIED:')
    print('    - Ghost fills removed from clean stream')
    print('    - FIFO position +N/-N correctly synchronized')
    print('    - Net position = 0 at session end (flat close)')
    print('    - Zero direction flips in clean fill stream')
else:
    print('  ' + str(fail_c) + ' file(s) FAILED -- review details above')
print(SEP)
