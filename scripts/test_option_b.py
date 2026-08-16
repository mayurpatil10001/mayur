import os, sys, sqlite3, logging, dataclasses

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, clear_rejected_fills, pair_fills_to_trades, verify_sequence, FillRecord, _OpenLeg, _make_round_trip
)

# Custom pair_fills_to_trades with Option B fix
def pair_fills_to_trades_option_b(
    fills              : list[FillRecord],
    ghost_fills_dropped: int = 0,
):
    trades   = []
    queue    : list[_OpenLeg]  = []
    position : int             = 0

    sorted_fills = sorted(fills, key=lambda f: (f.ts_val, f.position_order))

    for f in sorted_fills:
        if not f.is_valid():
            continue

        qty   = f.quantity
        side  = f.side
        delta = +qty if side == "BUY" else -qty
        new_pos = position + delta

        # ---- FLIP: crosses zero ----------------------------------------
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

        # ---- EXIT / SCALE-OUT: moving toward zero ----------------------
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
                    op.qty    -= to_close
                    to_close   = 0
                    trades.append(_make_round_trip(partial, f))
            position = new_pos
            continue

        # ---- ENTRY / SCALE-IN: moving away from zero -------------------
        if new_pos != 0 and (position == 0 or abs(new_pos) > abs(position)):
            if position == 0 and getattr(f, "open_close", "").upper() == "CLOSE":
                if ghost_fills_dropped > 0:
                    continue
                else:
                    pass
            new_contracts = abs(new_pos) - abs(position)
            queue.append(_OpenLeg(fill=f, side=side, qty=new_contracts,
                                  price=f.price, time_str=f.timestamp))
            position = new_pos
            continue

        # ---- NO-OP (flat -> flat, or unchanged) ------------------------
        position = new_pos

    # OPTION B FIX: Create FillRecord copies with quantity set to remaining op.qty
    unpaired = []
    for op in queue:
        # Create adjusted FillRecord with op.qty
        f_copy = dataclasses.replace(op.fill, quantity=op.qty)
        unpaired.append(f_copy)

    return trades, unpaired

db = sqlite3.connect(os.path.join(PROJECT_ROOT, 'trading_platform_clean_v2.db'))
db.row_factory = sqlite3.Row

import random
random.seed(99)
all_pure = db.execute(
    "SELECT account, trade_date FROM file_audit WHERE integrity_ok=0 "
    "AND flag_reason NOT LIKE '%rejected_fills%' ORDER BY account, trade_date"
).fetchall()
sample25 = random.sample(list(all_pure), 25)

random.seed(42)
sample25_set = {(r['account'], r['trade_date']) for r in sample25}
candidates_all = [(r['account'], r['trade_date']) for r in all_pure
                  if (r['account'], r['trade_date']) not in sample25_set]
additional30 = random.sample(candidates_all, min(30, len(candidates_all)))

sample42_files = [(r['account'], r['trade_date']) for r in sample25] + additional30

# Test original vs Option B on sample files
print(f"Testing original vs Option B on {len(sample42_files)} sample files...\n")

orig_fails = 0
optb_fails = 0

for acct, date in sample42_files:
    fn = f"TradeActivityLog_{date}_UTC.{acct}.data"
    fp = os.path.join(PROJECT_ROOT, "dataset", fn)
    if not os.path.exists(fp):
        continue
    raw, _ = _parse_file_nitro(fp)
    clear_rejected_fills()
    fills = GhostFillEngine.from_dicts(raw)

    # 1. Original run
    engine_orig = GhostFillEngine()
    res_orig = engine_orig.process(fills)
    if not res_orig.integrity_ok:
        orig_fails += 1

    # 2. Option B run (with adjusted unpaired fill quantities)
    # We simulate process with pair_fills_to_trades_option_b
    fills_b = GhostFillEngine.from_dicts(raw)
    fills_sorted = sorted(fills_b, key=lambda f: (f.ts_val, f.position_order))
    from collections import defaultdict
    groups = defaultdict(list)
    for f in fills_sorted:
        groups[f.base_symbol].append(f)

    all_ok = True
    for bs, sym_fills in groups.items():
        # filter ghosts
        ghosts = [f for f in sym_fills if f.suggests_ghost]
        clean_cand = [f for f in sym_fills if not f.suggests_ghost]
        trades, unpaired = pair_fills_to_trades_option_b(clean_cand, ghost_fills_dropped=len(ghosts))
        ok, msgs, flip_count = verify_sequence(sym_fills, clean_cand, trades, unpaired)
        if not ok:
            all_ok = False
            # print reason
            print(f"[{acct} {date} {bs}] FAIL: {msgs}")

    if not all_ok:
        optb_fails += 1

print(f"\nOriginal integrity failures: {orig_fails} / {len(sample42_files)}")
print(f"Option B integrity failures: {optb_fails} / {len(sample42_files)}")
