import sqlite3
db = sqlite3.connect('trading_platform_clean_v2.db')
db.row_factory = sqlite3.Row

cats = db.execute(
    "SELECT flag_reason, COUNT(*) n FROM file_audit WHERE integrity_ok=0 GROUP BY flag_reason ORDER BY n DESC LIMIT 8"
).fetchall()
print('flag_reason categories (all failures):')
for r in cats:
    print(f"  {r['n']:6,}  [{r['flag_reason']}]")

pure = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason='integrity_fail'"
).fetchone()[0]
ghost_orphan = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason LIKE '%rejected%'"
).fetchone()[0]

print()
print(f"Pure integrity fails (flag_reason='integrity_fail') : {pure:,}")
print(f"Guard-triggered fails (has rejected_fills in reason): {ghost_orphan:,}")
print()

pure_ghost0 = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason='integrity_fail' AND ghost_fills=0"
).fetchone()[0]
pure_ghost1 = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason='integrity_fail' AND ghost_fills>0"
).fetchone()[0]
print(f"  Pure fails with ghost_fills=0 : {pure_ghost0:,}")
print(f"  Pure fails with ghost_fills>0 : {pure_ghost1:,}")

twofill_pure = db.execute(
    "SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0 AND flag_reason='integrity_fail' AND total_raw_fills=2"
).fetchone()[0]
print(f"  2-fill pure integrity fails   : {twofill_pure:,}")

total_files = db.execute("SELECT COUNT(*) FROM file_audit").fetchone()[0]
print()
print(f"Pure fail rate v3.2  : {pure}/{total_files} = {pure/total_files*100:.2f}%")
print(f"Pre-fix (v3) baseline: 1,006 / ~38,700 = 2.60%")
print(f"If same rate today   : {int(total_files*0.026):,} expected")
print(f"Actual pure fails    : {pure:,}")
print()

# Summary table
total_fail = db.execute("SELECT COUNT(*) FROM file_audit WHERE integrity_ok=0").fetchone()[0]
print("=== FINAL FOUR-WAY BREAKDOWN ===")
print(f"Total failures              : {total_fail:,}")
print(f"  A. Pure natural fails     : {pure:,}  (flag='integrity_fail', no rejected_fills)")
print(f"     - ghost_fills=0        : {pure_ghost0:,}")
print(f"     - ghost_fills>0        : {pure_ghost1:,}")
print(f"  B. Guard-triggered fails  : {ghost_orphan:,}  (flag includes 'rejected_fills=N')")
print(f"     - Correctly exposed    : ghost_orphan CLOSEs rejected by v3.2 guard")
print(f"     - In v3 (no guard):    these were INCORRECTLY passing via fake-trade-balancing")
print()
print("KEY: The pre-fix (v3) baseline of 1,006 DID NOT include category B failures")
print("     because the guard did not exist -- those files silently passed with fake trades.")
print("     With v3.2, they are correctly identified as integrity failures.")
db.close()
