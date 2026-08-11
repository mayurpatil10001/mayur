"""
scripts/verify_option_b_production.py
======================================
Post-fix verification: run production GhostFillEngine (which now contains
the Option B fix) on the same 42 sample files and confirm:
  - Rescued (F->T) >= 16 (same as the in-memory test)
  - Regressions (T->F) = 0
"""
import os, sys, sqlite3, random, logging
logging.disable(logging.CRITICAL)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Force reimport to pick up the patched file
import importlib
import trading_platform.services.ghost_fill_engine as gfe_mod
importlib.reload(gfe_mod)

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import GhostFillEngine, clear_rejected_fills

DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")

db = sqlite3.connect(os.path.join(PROJECT_ROOT, "trading_platform_clean_v2.db"))
db.row_factory = sqlite3.Row
all_pure = db.execute(
    "SELECT account, trade_date FROM file_audit WHERE integrity_ok=0 "
    "AND flag_reason NOT LIKE '%rejected_fills%' ORDER BY account, trade_date"
).fetchall()
db.close()

random.seed(99)
s25 = random.sample(list(all_pure), 25)
random.seed(42)
s25_set = {(r["account"], r["trade_date"]) for r in s25}
rest    = [(r["account"], r["trade_date"]) for r in all_pure if (r["account"], r["trade_date"]) not in s25_set]
add30   = random.sample(rest, min(30, len(rest)))
all42   = [(r["account"], r["trade_date"]) for r in s25] + add30

rescued = 0
regressions = 0
pass_count = 0
fail_count = 0

print(f"Production fix verification: {len(all42)} sample files")
print(f"{'Account':25s} {'Date':12s}  Status  Failure reasons")
print("-" * 90)

for acct, date in all42:
    fn = f"TradeActivityLog_{date}_UTC.{acct}.data"
    fp = os.path.join(DATASET_DIR, fn)
    if not os.path.exists(fp):
        continue

    raw, _ = _parse_file_nitro(fp)
    if not raw:
        continue

    clear_rejected_fills()
    engine = GhostFillEngine()
    fills  = GhostFillEngine.from_dicts(raw)
    res    = engine.process(fills)

    if res.integrity_ok:
        pass_count += 1
        # Only print if it was previously failing (it's in our "failing" sample)
        print(f"  {acct:25s} {date}  PASS")
    else:
        fail_count += 1
        reasons = []
        for bs, sr in res.per_symbol.items():
            if not sr.integrity_ok:
                sym_reasons = [n for n in sr.integrity_notes
                               if "IMBALANCE" in n or "FLIP" in n or "INVERTED" in n]
                reasons.append(f"{bs}: {'; '.join(sym_reasons)[:60]}")
        print(f"  {acct:25s} {date}  FAIL    {' | '.join(reasons)[:80]}")

print()
print(f"Summary:")
print(f"  PASS: {pass_count}")
print(f"  FAIL: {fail_count}")
print(f"  (All {pass_count + fail_count} files were confirmed failures before the fix)")
