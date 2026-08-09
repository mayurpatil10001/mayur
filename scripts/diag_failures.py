import sqlite3

db = sqlite3.connect('trading_platform_clean_v2.db')
db.row_factory = sqlite3.Row

total = db.execute('SELECT COUNT(*) FROM file_audit').fetchone()[0]
fail  = db.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0').fetchone()[0]

bypass_fail   = db.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND bypass_mode=1').fetchone()[0]
nobypass_fail = db.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND bypass_mode=0').fetchone()[0]
ghost_fail    = db.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND ghost_fills>0').fetchone()[0]
noghost_fail  = db.execute('SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND ghost_fills=0').fetchone()[0]

flag_reasons = db.execute(
    'SELECT flag_reason, COUNT(*) as n FROM file_audit WHERE integrity_ok=0 GROUP BY flag_reason ORDER BY n DESC LIMIT 15'
).fetchall()

sample_noghost = db.execute(
    'SELECT account, trade_date, total_raw_fills, ghost_fills, bypass_mode, note_coverage, integrity_notes '
    'FROM file_audit WHERE integrity_ok=0 AND ghost_fills=0 '
    'ORDER BY total_raw_fills ASC LIMIT 10'
).fetchall()

sample_bypass = db.execute(
    'SELECT account, trade_date, total_raw_fills, ghost_fills, bypass_mode, note_coverage, integrity_notes '
    'FROM file_audit WHERE integrity_ok=0 AND bypass_mode=1 '
    'ORDER BY total_raw_fills ASC LIMIT 5'
).fetchall()

print('=== FAILURE BREAKDOWN ===')
print(f'Total failures      : {fail:,} / {total:,} ({fail/total*100:.1f}%)')
print(f'  bypass_mode=1     : {bypass_fail:,} ({bypass_fail/fail*100:.1f}% of fails)')
print(f'  bypass_mode=0     : {nobypass_fail:,} ({nobypass_fail/fail*100:.1f}% of fails)')
print(f'  ghost_fills>0     : {ghost_fail:,} ({ghost_fail/fail*100:.1f}% of fails)')
print(f'  ghost_fills=0     : {noghost_fail:,} ({noghost_fail/fail*100:.1f}% of fails)')
print()
print('=== FLAG REASON BREAKDOWN (failing files) ===')
for row in flag_reasons:
    reason = (row['flag_reason'] or '(none)')[:80]
    print(f'  {row["n"]:6,}  {reason}')
print()
print('=== SAMPLE: ghost=0 failures (smallest) ===')
for r in sample_noghost:
    notes = (r['integrity_notes'] or '')[:140]
    print(f'  {r["account"]:25s} {r["trade_date"]}  raw={r["total_raw_fills"]:4d}  bypass={r["bypass_mode"]}  nc={r["note_coverage"]:.0%}')
    print(f'    {notes}')
print()
print('=== SAMPLE: bypass=1 failures ===')
for r in sample_bypass:
    notes = (r['integrity_notes'] or '')[:140]
    print(f'  {r["account"]:25s} {r["trade_date"]}  raw={r["total_raw_fills"]:4d}  ghosts={r["ghost_fills"]}  nc={r["note_coverage"]:.0%}')
    print(f'    {notes}')

db.close()
