"""
Step 4a: Fill-by-fill FIFO trace for 2026-07-09 IPS_TM_7 NQ
Same methodology used to diagnose Jun-23 and Jul-02 cases.
$7,550 PnL swing from 1 dropped fill -- root cause UNKNOWN entering this task.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, FillRecord, classify_fill, pair_fills_to_trades
)

DATE    = "2026-07-09"
ACCT    = "IPS_TM_7"
FPATH   = f"dataset/TradeActivityLog_{DATE}_UTC.{ACCT}.data"

raw, _ = _parse_file_nitro(FPATH)
nq_raw = [f for f in raw if "NQ" in str(f.get("symbol", ""))]
fills  = GhostFillEngine.from_dicts(nq_raw)
fills_sorted = sorted(fills, key=lambda f: (f.ts_val, f.position_order))

print(f"\n{'='*80}")
print(f"Step 4a: {DATE} | {ACCT} NQ")
print(f"{'='*80}")
print(f"Total NQ fills: {len(fills_sorted)}")

# Print fill table
print(f"\nIDX | {'TIMESTAMP':>19} | SIDE | QTY | {'PRICE':>10} | OC    | GHOST | NOTE_LEN | NOTE/MSG")
print("-"*120)
ghost_idxs = []
for i, f in enumerate(fills_sorted):
    is_ghost = classify_fill(f)
    if is_ghost:
        ghost_idxs.append(i)
    note_len = "GHOST" if (not f.note or not f.note.strip()) and len(f.msgtxt) > 10 else "real"
    print(f"{i:>3} | {f.timestamp[:19]:>19} | {f.side:>4} | {f.quantity:>3} | {f.price:>10.2f} | {f.open_close:>5} | {'YES' if is_ghost else 'no':>5} | {note_len:>8} | note={repr(f.note[:20])} msg={repr(f.msgtxt[:50])}")

print(f"\n--- GHOST FILLS (classified ghost=True) ---")
if not ghost_idxs:
    print("  None found.")
for gi in ghost_idxs:
    g = fills_sorted[gi]
    print(f"  IDX={gi} | {g.timestamp[:19]} | {g.side} {g.quantity}x @ {g.price:.2f}")
    print(f"    open_close     = {g.open_close}")
    print(f"    note           = {repr(g.note)}")
    print(f"    msgtxt         = {repr(g.msgtxt[:120])}")
    print(f"    position_order = {g.position_order}")

# Dirty FIFO
dirty_trades, dirty_unpaired = pair_fills_to_trades(fills_sorted)
dirty_net = sum(t.pnl_dollars for t in dirty_trades)
dirty_wins = sum(1 for t in dirty_trades if t.pnl_dollars > 0)
print(f"\n--- DIRTY FIFO (all fills) ---")
print(f"  Trades: {len(dirty_trades)} | Wins: {dirty_wins} | Net: ${dirty_net:+,.2f}")
for t in dirty_trades:
    sign = "+" if t.pnl_dollars >= 0 else ""
    print(f"    {t.direction:>5}  {t.quantity}x @ entry={t.entry_price:.2f} exit={t.exit_price:.2f} | {t.entry_time[:19]} -> {t.exit_time[:19]} | {sign}${t.pnl_dollars:,.2f}")

# Clean FIFO
clean_fills = [f for f in fills_sorted if not classify_fill(f)]
clean_trades, clean_unpaired = pair_fills_to_trades(clean_fills)
clean_net = sum(t.pnl_dollars for t in clean_trades)
clean_wins = sum(1 for t in clean_trades if t.pnl_dollars > 0)
print(f"\n--- CLEAN FIFO (ghosts removed) ---")
print(f"  Trades: {len(clean_trades)} | Wins: {clean_wins} | Net: ${clean_net:+,.2f}")
for t in clean_trades:
    sign = "+" if t.pnl_dollars >= 0 else ""
    print(f"    {t.direction:>5}  {t.quantity}x @ entry={t.entry_price:.2f} exit={t.exit_price:.2f} | {t.entry_time[:19]} -> {t.exit_time[:19]} | {sign}${t.pnl_dollars:,.2f}")

print(f"\n--- DELTA SUMMARY ---")
print(f"  Dirty Net: ${dirty_net:+,.2f}  |  Clean Net: ${clean_net:+,.2f}  |  Delta: ${clean_net-dirty_net:+,.2f}")
print(f"  Fills removed as ghost: {len(ghost_idxs)}")

# For each ghost, do fill-by-fill trace around that index
for gi in ghost_idxs:
    ctx_start = max(0, gi - 5)
    ctx_end   = min(len(fills_sorted) - 1, gi + 8)

    def run_fifo_trace(fill_list, label, trace_from, trace_end_idx, all_fills):
        print(f"\n  --- {label} FIFO TRACE (IDX {trace_from}-{trace_end_idx}) ---")
        position = 0
        queue = []  # (side, price, qty, ts)

        # Fast-forward position state from fill 0 to trace_from-1
        for f in all_fills[:trace_from]:
            if not f.is_valid():
                continue
            delta = +f.quantity if f.side == "BUY" else -f.quantity
            new_pos = position + delta
            if position != 0 and new_pos != 0 and (position > 0) != (new_pos > 0):
                queue.clear()
                if new_pos != 0:
                    queue.append((f.side, f.price, abs(new_pos), f.timestamp))
            elif abs(new_pos) < abs(position) and (new_pos == 0 or (position > 0) == (new_pos > 0)):
                to_close = abs(position) - abs(new_pos)
                while to_close > 0 and queue:
                    es, ep, eq, et = queue[0]
                    if eq <= to_close:
                        to_close -= eq
                        queue.pop(0)
                    else:
                        queue[0] = (es, ep, eq - to_close, et)
                        to_close = 0
            elif new_pos != 0:
                add = abs(new_pos) - abs(position)
                if add > 0:
                    queue.append((f.side, f.price, add, f.timestamp))
            position = new_pos

        print(f"  Pre-trace state: pos={position:+}, queue=[{', '.join(f'S{q}@{p:.2f}' if s=='SELL' else f'L{q}@{p:.2f}' for s,p,q,_ in queue)}]")

        for i in range(trace_from, trace_end_idx + 1):
            if i >= len(all_fills):
                break
            f = all_fills[i]
            if not f.is_valid():
                continue
            orig_idx = i
            delta   = +f.quantity if f.side == "BUY" else -f.quantity
            new_pos = position + delta
            is_ghost = classify_fill(f)
            tag = " <<GHOST>>" if is_ghost else ""

            print(f"  IDX={orig_idx:>3} {f.timestamp[:19]} {f.side:>4} {f.quantity:>2}x @ {f.price:>10.2f} OC={f.open_close:>5} | pos {position:>+4} -> {new_pos:>+4} | queue={len(queue)}{tag}")

            if position != 0 and new_pos != 0 and (position > 0) != (new_pos > 0):
                print(f"         ACTION=FLIP: close {len(queue)} leg(s), open {abs(new_pos)}")
                while queue:
                    es, ep, eq, et = queue.pop(0)
                    d = "LONG" if es == "BUY" else "SHORT"
                    pnl = ((f.price - ep) if d == "LONG" else (ep - f.price)) * 20 * eq
                    print(f"           EMIT {d} {eq}x {ep:.2f}->{f.price:.2f} = ${pnl:+,.2f}  entry={et[:19]}")
                if new_pos != 0:
                    queue.append((f.side, f.price, abs(new_pos), f.timestamp))
            elif abs(new_pos) < abs(position) and (new_pos == 0 or (position > 0) == (new_pos > 0)):
                to_close = abs(position) - abs(new_pos)
                print(f"         ACTION=EXIT/SCALE-OUT: close {to_close} contracts")
                remaining = to_close
                while remaining > 0 and queue:
                    es, ep, eq, et = queue[0]
                    close_n = min(eq, remaining)
                    d = "LONG" if es == "BUY" else "SHORT"
                    pnl = ((f.price - ep) if d == "LONG" else (ep - f.price)) * 20 * close_n
                    print(f"           EMIT {d} {close_n}x {ep:.2f}->{f.price:.2f} = ${pnl:+,.2f}  entry={et[:19]}")
                    if eq <= remaining:
                        remaining -= eq
                        queue.pop(0)
                    else:
                        queue[0] = (es, ep, eq - remaining, et)
                        remaining = 0
            elif new_pos != 0 and abs(new_pos) >= abs(position):
                add = abs(new_pos) - abs(position)
                if add > 0:
                    queue.append((f.side, f.price, add, f.timestamp))
                    print(f"         ACTION=ENTRY/SCALE-IN: +{add} @ {f.price:.2f}")

            position = new_pos

        q_str = ", ".join(f"{'L' if s=='BUY' else 'S'}{q}@{p:.2f}" for s,p,q,_ in queue)
        print(f"  End state: pos={position:+}, queue=[{q_str}]")

    print(f"\n{'='*60}")
    print(f"FILL-BY-FILL TRACE around IDX={gi} (context IDX {ctx_start}-{ctx_end})")
    print(f"{'='*60}")

    run_fifo_trace(fills_sorted, "DIRTY", ctx_start, ctx_end, fills_sorted)
    clean_sorted = [f for f in fills_sorted if not classify_fill(f)]
    run_fifo_trace(clean_sorted, "CLEAN (ghost removed)", ctx_start, ctx_end, clean_sorted)

print(f"\nStep 4a COMPLETE. Review findings above before proceeding to Step 1.")
