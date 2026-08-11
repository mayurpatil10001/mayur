"""
scripts/test_option_b_fix.py
=============================
Small-sample test of the Option B fix BEFORE applying it to production code.

What we test
------------
The 19 confirmed "CLOSED_NEXT_DAY" files from Step 2, plus all 25 original
sample files (seed=99) and the 30 additional files (seed=42), = 42 total files.

For each file we run the pipeline TWICE:
  (a) ORIGINAL  -- exactly as production today
  (b) PATCHED   -- pair_fills_to_trades() with the Option B fix applied to
                   the local copy of the function, verify_sequence unchanged

The fix: in pair_fills_to_trades(), the final `unpaired` list was built as:
    unpaired = [op.fill for op in queue]
This returns the ORIGINAL fill object, whose .quantity is the full fill size.
But when a FLIP occurred, _OpenLeg.qty holds only the PARTIAL remaining
position (abs(new_pos)), which is less than op.fill.quantity.
verify_sequence then computes expected_open from the full fill qty, so
  net (actual partial position at end) != expected_open (full fill qty)
triggering a false POSITION IMBALANCE.

Fix: replace op.fill with a quantity-corrected copy when op.qty != op.fill.quantity.
    unpaired = [
        op.fill if op.qty == op.fill.quantity
        else dc_replace(op.fill, quantity=op.qty)
        for op in queue
    ]

Expected result on the 19 CLOSED_NEXT_DAY files:
  Files where the ONLY failure was POSITION IMBALANCE (not DIRECTION FLIPS)
  should flip from False -> True.
  Files with DIRECTION FLIPS will still fail (separate issue).

This script reports exactly which files change and which don't.
"""
import os, sys, sqlite3, random, logging
from dataclasses import replace as dc_replace
from collections import defaultdict

logging.disable(logging.CRITICAL)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, clear_rejected_fills,
    pair_fills_to_trades, verify_sequence,
    FillRecord, _OpenLeg, _make_round_trip,
)

DATASET_DIR = os.path.join(PROJECT_ROOT, "dataset")

# ── Patched pair_fills_to_trades ──────────────────────────────────────────
def pair_fills_to_trades_patched(fills, ghost_fills_dropped=0):
    """
    Identical to production pair_fills_to_trades() except:
    unpaired uses op.qty (PARTIAL remaining position) instead of
    op.fill.quantity (full fill size) — the Option B fix.
    """
    trades   = []
    queue    = []   # List[_OpenLeg]
    position = 0

    sorted_fills = sorted(fills, key=lambda f: (f.ts_val, f.position_order))

    for f in sorted_fills:
        if not f.is_valid():
            continue

        qty   = f.quantity
        side  = f.side
        delta = +qty if side == "BUY" else -qty
        new_pos = position + delta

        # FLIP: crosses zero
        if position != 0 and new_pos != 0 and (position > 0) != (new_pos > 0):
            while queue:
                op = queue.pop(0)
                trades.append(_make_round_trip(op, f))
            position = 0
            new_contracts = abs(new_pos)
            queue.append(_OpenLeg(fill=f, side=side, qty=new_contracts,
                                  price=f.price, time_str=f.timestamp))
            position = new_pos
            continue

        # EXIT / SCALE-OUT
        if position != 0 and abs(new_pos) < abs(position) and (
            new_pos == 0 or (position > 0) == (new_pos > 0)
        ):
            to_close = abs(position) - abs(new_pos)
            while to_close > 0 and queue:
                op = queue[0]
                if op.qty <= to_close:
                    to_close -= op.qty
                    queue.pop(0)
                    trades.append(_make_round_trip(op, f))
                else:
                    partial = _OpenLeg(fill=op.fill, side=op.side,
                                       qty=to_close, price=op.price,
                                       time_str=op.time_str)
                    op.qty   -= to_close
                    to_close  = 0
                    trades.append(_make_round_trip(partial, f))
            position = new_pos
            continue

        # ENTRY / SCALE-IN
        if new_pos != 0 and (position == 0 or abs(new_pos) > abs(position)):
            if position == 0 and getattr(f, "open_close", "").upper() == "CLOSE":
                if ghost_fills_dropped > 0:
                    continue   # ORPHANED_CLOSE_POST_GHOST_OPEN — reject
                # else: ORPHANED_CLOSE_UNKNOWN_ORIGIN — fall through
            new_contracts = abs(new_pos) - abs(position)
            queue.append(_OpenLeg(fill=f, side=side, qty=new_contracts,
                                  price=f.price, time_str=f.timestamp))
            position = new_pos
            continue

        position = new_pos  # NO-OP

    # ── OPTION B FIX ──────────────────────────────────────────────────────
    # Use op.qty (remaining partial position) rather than op.fill.quantity
    # (full fill size). When a FLIP occurred, op.qty < op.fill.quantity,
    # and returning the full fill quantity causes verify_sequence's
    # expected_open to diverge from the actual net position.
    unpaired = [
        op.fill if op.qty == op.fill.quantity
        else dc_replace(op.fill, quantity=op.qty)
        for op in queue
    ]
    return trades, unpaired


# ── Helpers ───────────────────────────────────────────────────────────────
def run_both(fp: str):
    raw, _ = _parse_file_nitro(fp)
    if not raw:
        return None, None

    def _process_with(pairer):
        clear_rejected_fills()
        fills_all = GhostFillEngine.from_dicts(raw)
        fills_sorted = sorted(fills_all, key=lambda f: (f.ts_val, f.position_order))
        groups = defaultdict(list)
        for f in fills_sorted:
            groups[f.base_symbol].append(f)

        results = {}
        for bs, sym_fills in sorted(groups.items()):
            ghosts = [f for f in sym_fills if f.suggests_ghost]
            clean  = [f for f in sym_fills if not f.suggests_ghost]
            from trading_platform.services.ghost_fill_engine import _dedup_fills
            deduped = _dedup_fills(clean)
            trades, unpaired = pairer(deduped, ghost_fills_dropped=len(ghosts))
            ok, msgs, flips  = verify_sequence(sym_fills, deduped, trades, unpaired)
            results[bs] = {
                "ok": ok,
                "msgs": [m for m in msgs if "IMBALANCE" in m or "FLIP" in m or "INVERTED" in m],
                "flips": flips,
                "unpaired": len(unpaired),
            }
        return results

    orig    = _process_with(pair_fills_to_trades)
    patched = _process_with(pair_fills_to_trades_patched)
    return orig, patched


# ── Load sample files ──────────────────────────────────────────────────────
db = sqlite3.connect(os.path.join(PROJECT_ROOT, "trading_platform_clean_v2.db"))
db.row_factory = sqlite3.Row
all_pure = db.execute(
    "SELECT account, trade_date FROM file_audit WHERE integrity_ok=0 "
    "AND flag_reason NOT LIKE '%rejected_fills%' ORDER BY account, trade_date"
).fetchall()
db.close()

random.seed(99)
sample25 = random.sample(list(all_pure), 25)
random.seed(42)
s25_set  = {(r["account"], r["trade_date"]) for r in sample25}
rest     = [(r["account"], r["trade_date"]) for r in all_pure if (r["account"], r["trade_date"]) not in s25_set]
add30    = random.sample(rest, min(30, len(rest)))
all42    = [(r["account"], r["trade_date"]) for r in sample25] + add30

# ── Run ────────────────────────────────────────────────────────────────────
print(f"Option B fix test on {len(all42)} sample files")
print(f"{'Account':25s} {'Date':12s}  {'Orig':5s} -> {'Patch':5s}  notes")
print("-" * 85)

orig_fails = 0
patch_fails = 0
rescued = 0
unaffected_fails = 0

for acct, date in all42:
    fn = f"TradeActivityLog_{date}_UTC.{acct}.data"
    fp = os.path.join(DATASET_DIR, fn)
    if not os.path.exists(fp):
        print(f"  {acct:25s} {date}  MISSING")
        continue

    orig, patched = run_both(fp)
    if orig is None:
        continue

    # File-level pass/fail
    orig_ok   = all(v["ok"] for v in orig.values())
    patch_ok  = all(v["ok"] for v in patched.values())

    if not orig_ok:
        orig_fails += 1
    if not patch_ok:
        patch_fails += 1

    if not orig_ok and patch_ok:
        rescued += 1
        notes_str = "; ".join(
            f"{bs}: {', '.join(v['msgs'])}"
            for bs, v in orig.items() if not v["ok"]
        )
        print(f"  {acct:25s} {date}  FAIL  -> PASS   was: {notes_str[:60]}")
    elif not orig_ok and not patch_ok:
        unaffected_fails += 1
        # Show what changed at symbol level
        changes = []
        for bs in orig:
            if orig[bs]["msgs"] != patched[bs]["msgs"]:
                changes.append(f"{bs}: {orig[bs]['msgs']} -> {patched[bs]['msgs']}")
        change_str = " | ".join(changes) if changes else "no change"
        print(f"  {acct:25s} {date}  FAIL  -> FAIL   {change_str[:60]}")
    elif orig_ok and not patch_ok:
        print(f"  {acct:25s} {date}  PASS  -> FAIL   *** REGRESSION ***")
    # else: PASS -> PASS, don't print

print()
print(f"Results across {len(all42)} files:")
print(f"  Original failures:    {orig_fails}")
print(f"  Patched failures:     {patch_fails}")
print(f"  Rescued (F->T):       {rescued}")
print(f"  Still failing:        {unaffected_fails}")
print(f"  Regressions (T->F):   {orig_fails + rescued - patch_fails - unaffected_fails}")
