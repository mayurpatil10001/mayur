"""
scripts/step1_reconcile_gap.py
=================================
Step 1: Reconcile the 955-file gap.
Show all three queries and their raw output side-by-side.
Find exactly what is in the gap (files not matching Category A or B).
"""
import sqlite3

DB = 'trading_platform_clean_v2.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

print("=" * 80)
print("  STEP 1-0: SCHEMA — relevant columns in file_audit")
print("=" * 80)
cols = db.execute("PRAGMA table_info(file_audit)").fetchall()
for c in cols:
    print(f"  col {c['cid']:2d}: {c['name']:30s} {c['type']}")

print()
print("=" * 80)
print("  STEP 1-1: THE THREE COUNTS SIDE BY SIDE")
print("=" * 80)

total_fail = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0"
).fetchone()[0]

cat_a = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason='integrity_fail'"
).fetchone()[0]

cat_b = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason LIKE '%rejected_fills%'"
).fetchone()[0]

gap = total_fail - (cat_a + cat_b)

print(f"  TOTAL integrity failures (integrity_ok=0)            : {total_fail:,}")
print(f"  Category A (flag_reason='integrity_fail')            : {cat_a:,}")
print(f"  Category B (flag_reason LIKE '%rejected_fills%')     : {cat_b:,}")
print(f"  A + B sum                                            : {cat_a + cat_b:,}")
print(f"  GAP (total - A - B)                                  : {gap:,}")

print()
print("=" * 80)
print("  STEP 1-2: ALL DISTINCT flag_reason VALUES FOR integrity_ok=0")
print("=" * 80)
all_reasons = db.execute(
    "SELECT flag_reason, COUNT(*) n FROM file_audit WHERE integrity_ok=0 "
    "GROUP BY flag_reason ORDER BY n DESC"
).fetchall()
for r in all_reasons:
    reason = repr(r['flag_reason'])
    print(f"  {r['n']:6,}  {reason}")

print()
print("=" * 80)
print("  STEP 1-3: FILES IN THE GAP (not Category A, not Category B)")
print("=" * 80)
gap_files = db.execute(
    "SELECT account, trade_date, total_raw_fills, ghost_fills, bypass_mode, "
    "       note_coverage, flag_reason, integrity_notes "
    "FROM file_audit "
    "WHERE integrity_ok=0 "
    "  AND flag_reason != 'integrity_fail' "
    "  AND (flag_reason NOT LIKE '%rejected_fills%' OR flag_reason IS NULL) "
    "ORDER BY account, trade_date "
    "LIMIT 30"
).fetchall()

gap_count = db.execute(
    "SELECT COUNT(*) FROM file_audit "
    "WHERE integrity_ok=0 "
    "  AND flag_reason != 'integrity_fail' "
    "  AND (flag_reason NOT LIKE '%rejected_fills%' OR flag_reason IS NULL)"
).fetchone()[0]

print(f"  Total gap files: {gap_count:,}")
print()
print(f"  {'Account':25s} {'Date':12s} {'raw':5s} {'ghosts':7s} {'bypass':7s} {'nc':5s}  flag_reason")
print("  " + "-" * 90)
for r in gap_files:
    reason = (r['flag_reason'] or 'NULL')[:40]
    print(f"  {r['account']:25s} {r['trade_date']:12s} {r['total_raw_fills']:5d} "
          f"{r['ghost_fills']:7d} {r['bypass_mode']:7d} {r['note_coverage']:.0%}  {reason}")

print()
print("=" * 80)
print("  STEP 1-4: DISTINCT flag_reason VALUES IN THE GAP")
print("=" * 80)
gap_reasons = db.execute(
    "SELECT flag_reason, COUNT(*) n FROM file_audit "
    "WHERE integrity_ok=0 "
    "  AND flag_reason != 'integrity_fail' "
    "  AND (flag_reason NOT LIKE '%rejected_fills%' OR flag_reason IS NULL) "
    "GROUP BY flag_reason ORDER BY n DESC"
).fetchall()
for r in gap_reasons:
    print(f"  {r['n']:6,}  {repr(r['flag_reason'])}")

print()
print("=" * 80)
print("  STEP 1-5: CHECK FOR DOUBLE-COUNTING (A AND B simultaneously)")
print("=" * 80)
double = db.execute(
    "SELECT COUNT(*) FROM file_audit "
    "WHERE integrity_ok=0 "
    "  AND flag_reason='integrity_fail' "
    "  AND flag_reason LIKE '%rejected_fills%'"
).fetchone()[0]
print(f"  Files satisfying BOTH A AND B conditions: {double:,}")

print()
print("=" * 80)
print("  STEP 1-6: RECONCILED EXACT BREAKDOWN")
print("=" * 80)
print(f"  Total integrity failures               : {total_fail:,}")
print(f"  Category A (flag='integrity_fail')     : {cat_a:,}")
print(f"  Category B (flag LIKE 'rejected_fills'): {cat_b:,}")
print(f"  Category C (everything else)           : {gap_count:,}")
print(f"  A + B + C                              : {cat_a + cat_b + gap_count:,}")
match = "EXACT MATCH" if (cat_a + cat_b + gap_count) == total_fail else "MISMATCH!"
print(f"  Verification                           : {match}")

db.close()
