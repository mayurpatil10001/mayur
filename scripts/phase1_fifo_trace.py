"""
Phase 1 fill-by-fill trace — Jun 23 and Jul 02 IPS_TM_7 NQ cascade analysis.
Traces FIFO state fill-by-fill around ghost for both dirty and clean runs.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    FillRecord, GhostFillEngine, classify_fill, pair_fills_to_trades
)

CASES = [
    ('2026-06-23', 'dataset/TradeActivityLog_2026-06-23_UTC.IPS_TM_7.data', 9, 20),
    ('2026-07-02', 'dataset/TradeActivityLog_2026-07-02_UTC.IPS_TM_7.data', 30, 47),
]

for date, fp, trace_start, trace_end in CASES:
    raw, _ = _parse_file_nitro(fp)
    nq_raw = [f for f in raw if 'NQ' in str(f.get('symbol', ''))]
    fills  = GhostFillEngine.from_dicts(nq_raw)
    
    # Identify ghost
    ghost_idx = None
    for i, f in enumerate(fills):
        if classify_fill(f):
            ghost_idx = i
            break
    
    print(f"\n{'='*80}")
    print(f"PHASE 1 TRACE: {date} | Ghost at IDX={ghost_idx}")
    print(f"{'='*80}")
    print(f"Ghost fill detail:")
    g = fills[ghost_idx]
    print(f"  IDX={ghost_idx} | {g.timestamp[:19]} | {g.side} {g.quantity}x @ {g.price:.2f}")
    print(f"  open_close = {g.open_close}")
    print(f"  note       = {repr(g.note)}")
    print(f"  msgtxt     = {repr(g.msgtxt[:100])}")
    print(f"  position_order = {g.position_order}")
    
    def trace_fifo(fill_list, label, trace_from, trace_to):
        print(f"\n  --- {label} FIFO TRACE (fills {trace_from}-{trace_to}) ---")
        sorted_fills = sorted(fill_list, key=lambda f: (f.ts_val, f.position_order))
        position = 0
        queue = []
        trades_emitted = []
        
        for i, f in enumerate(sorted_fills):
            if not f.is_valid():
                continue
            qty   = f.quantity
            side  = f.side
            delta = +qty if side == 'BUY' else -qty
            new_pos = position + delta
            orig_idx = fills.index(f) if f in fills else -1
            
            if orig_idx < trace_from or orig_idx > trace_to:
                # still update position
                if position != 0 and new_pos != 0 and (position > 0) != (new_pos > 0):
                    queue.clear()
                    position = 0
                    if new_pos != 0:
                        queue.append((side, f.price, abs(new_pos), f.timestamp))
                    position = new_pos
                elif position != 0 and abs(new_pos) < abs(position) and (new_pos == 0 or (position > 0) == (new_pos > 0)):
                    to_close = abs(position) - abs(new_pos)
                    while to_close > 0 and queue:
                        e_side, e_price, e_qty, e_ts = queue[0]
                        if e_qty <= to_close:
                            to_close -= e_qty
                            queue.pop(0)
                        else:
                            queue[0] = (e_side, e_price, e_qty - to_close, e_ts)
                            to_close = 0
                    position = new_pos
                elif new_pos != 0 and (position == 0 or abs(new_pos) > abs(position)):
                    new_contracts = abs(new_pos) - abs(position)
                    queue.append((side, f.price, new_contracts, f.timestamp))
                    position = new_pos
                else:
                    position = new_pos
                continue
            
            is_ghost = classify_fill(f)
            tag = ' <<GHOST>> ' if is_ghost else ''
            print(f"  IDX={orig_idx:>3} {f.timestamp[:19]} {side:>4} {qty:>2}x @ {f.price:>10.2f} OC={f.open_close:>5} | pos {position:>+4} -> {new_pos:>+4} | queue_len={len(queue)}{tag}")
            
            # show pairing action
            if position != 0 and new_pos != 0 and (position > 0) != (new_pos > 0):
                print(f"         ACTION=FLIP: close all {len(queue)} open legs, open {abs(new_pos)} new")
                while queue:
                    e_side, e_price, e_qty, e_ts = queue.pop(0)
                    ep, xp = e_price, f.price
                    d = 'LONG' if e_side == 'BUY' else 'SHORT'
                    pnl = ((xp - ep) if d == 'LONG' else (ep - xp)) * 20 * e_qty
                    print(f"           EMIT {d} {e_qty}x {ep:.2f}->{xp:.2f} = ${pnl:+,.2f}")
                position = 0
                if new_pos != 0:
                    queue.append((side, f.price, abs(new_pos), f.timestamp))
                position = new_pos
            elif position != 0 and abs(new_pos) < abs(position) and (new_pos == 0 or (position > 0) == (new_pos > 0)):
                to_close = abs(position) - abs(new_pos)
                print(f"         ACTION=EXIT/SCALE-OUT: close {to_close} contracts")
                remaining = to_close
                while remaining > 0 and queue:
                    e_side, e_price, e_qty, e_ts = queue[0]
                    close_lots = min(e_qty, remaining)
                    ep, xp = e_price, f.price
                    d = 'LONG' if e_side == 'BUY' else 'SHORT'
                    pnl = ((xp - ep) if d == 'LONG' else (ep - xp)) * 20 * close_lots
                    print(f"           EMIT {d} {close_lots}x {ep:.2f}->{xp:.2f} = ${pnl:+,.2f}  entry_ts={e_ts[:19]}")
                    if e_qty <= remaining:
                        remaining -= e_qty
                        queue.pop(0)
                    else:
                        queue[0] = (e_side, e_price, e_qty - remaining, e_ts)
                        remaining = 0
                position = new_pos
            elif new_pos != 0 and (position == 0 or abs(new_pos) > abs(position)):
                new_contracts = abs(new_pos) - abs(position)
                queue.append((side, f.price, new_contracts, f.timestamp))
                print(f"         ACTION=ENTRY/SCALE-IN: +{new_contracts} contracts @ {f.price:.2f}")
                position = new_pos
            else:
                position = new_pos
        
        q_str = ', '.join(f"{'L' if s=='BUY' else 'S'}{q}@{p:.2f}" for s,p,q,_ in queue)
        print(f"  End queue: [{q_str}] | Final position: {position}")
    
    # Trace dirty (ghost included)
    dirty_fills = sorted(fills, key=lambda f: (f.ts_val, f.position_order))
    trace_fifo(dirty_fills, "DIRTY", trace_start, trace_end)
    
    # Trace clean (ghost excluded)
    clean_fills = [f for f in fills if not classify_fill(f)]
    trace_fifo(clean_fills, "CLEAN (ghost removed)", trace_start, trace_end)
    
    print(f"\n  PHASE 1 CONCLUSION for {date}:")
    print(f"  Ghost IDX={ghost_idx}: {g.side} {g.quantity}x @ {g.price:.2f} | OC={g.open_close}")
    print(f"  The fill IS marked CLOSE by SC, with no strategy note.")
    print(f"  Without it, the NEXT OPEN fill absorbs the position close role,")
    print(f"  disconnecting all subsequent ENTRY/EXIT pairings downstream.")
