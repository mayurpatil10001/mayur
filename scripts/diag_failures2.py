import sqlite3

db = sqlite3.connect('trading_platform_clean_v2.db')
db.row_factory = sqlite3.Row

# What does verify_sequence say for 2-fill ghost=0 failures?
sample = db.execute(
    'SELECT account, trade_date, total_raw_fills, clean_trades, ghost_fills, integrity_notes '
    'FROM file_audit WHERE integrity_ok=0 AND ghost_fills=0 AND total_raw_fills=2 '
    'ORDER BY account LIMIT 15'
).fetchall()
print('=== 2-fill ghost=0 failures: integrity_notes ===')
for r in sample:
    notes = (r['integrity_notes'] or '')
    print(f'  {r["account"]:25s} {r["trade_date"]}  trades={r["clean_trades"]}  | {notes[:130]}')

# Top note patterns for ghost=0 failures
notes_counts = db.execute(
    'SELECT integrity_notes, COUNT(*) as n FROM file_audit '
    'WHERE integrity_ok=0 AND ghost_fills=0 '
    'GROUP BY integrity_notes ORDER BY n DESC LIMIT 10'
).fetchall()
print()
print('=== Top failure note patterns (ghost=0 failures) ===')
for r in notes_counts:
    n = (r['integrity_notes'] or '(null)')[:130]
    print(f'  {r["n"]:5,}  {n}')

# Rejected-fill breakdown for ghost=0 vs ghost>0
rej_ghost0   = db.execute("SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND ghost_fills=0 AND flag_reason LIKE '%rejected%'").fetchone()[0]
norej_ghost0 = db.execute("SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND ghost_fills=0 AND (flag_reason NOT LIKE '%rejected%' OR flag_reason IS NULL)").fetchone()[0]
rej_ghost1   = db.execute("SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND ghost_fills>0 AND flag_reason LIKE '%rejected%'").fetchone()[0]
norej_ghost1 = db.execute("SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND ghost_fills>0 AND (flag_reason NOT LIKE '%rejected%' OR flag_reason IS NULL)").fetchone()[0]

print()
print('=== Rejected-fill presence by ghost group ===')
print(f'ghost=0 WITH    rejected fills : {rej_ghost0:,}')
print(f'ghost=0 WITHOUT rejected fills : {norej_ghost0:,}')
print(f'ghost>0 WITH    rejected fills : {rej_ghost1:,}')
print(f'ghost>0 WITHOUT rejected fills : {norej_ghost1:,}')
print()

# Pure integrity fails (no rejected fills at all) — these are the true "natural" failures
pure_fail = norej_ghost0 + norej_ghost1
print(f'PURE integrity failures (no rejected fills, either ghost group): {pure_fail:,}')
print(f'  vs pre-fix (v3) baseline: ~1,006')
print(f'  dataset size ratio now vs then: 61,706 / ~38,700 = {61706/38700:.2f}x')
print(f'  scaled baseline estimate: {int(1006 * 61706/38700):,}')
print()
print('CONCLUSION:')
if pure_fail <= int(1006 * 61706/38700 * 1.2):
    print(f'  Natural failures ({pure_fail:,}) are within expected range of scaled baseline.')
else:
    print(f'  Natural failures ({pure_fail:,}) are ABOVE scaled baseline. Investigate further.')

db.close()
