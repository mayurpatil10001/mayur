"""
Step 1 — FIFO Contamination Trace
===================================
Simulate the current (buggy) pair_fills_to_trades() logic fill-by-fill
on a known-corrupted file and print the exact moment a cross-symbol
round-trip is created (entry leg symbol != exit leg symbol).
"""
import sys, os, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')

from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    GhostFillEngine, classify_fill, _dedup_fills, _base_symbol,
    _compute_note_rate, _make_round_trip, _OpenLeg
)

DATASET = 'dataset'

# TS_5 2026-06-01 is known to produce CL entries at ~30,683 (NQ-range price)
TARGET_FILES = [
    'dataset/TradeActivityLog_2026-06-01_UTC.TS_5.data',
    'dataset/TradeActivityLog_2026-06-01_UTC.TS_6.data',
]

SEP = '=' * 78

def trace_file(fp):
    fname = os.path.basename(fp)
    print(SEP)
    print('FILE:', fname)
    print(SEP)

    raw, _ = _parse_file_nitro(fp)
    fills = GhostFillEngine.from_dicts(raw)

    sym_counts = {}
    note_counts = {}
    for f in fills:
        bs = _base_symbol(f.symbol)
        sym_counts[bs] = sym_counts.get(bs, 0) + 1
        if f.note and f.note.strip():
            note_counts[bs] = note_counts.get(bs, 0) + 1

    print('Symbol breakdown:')
    for bs, cnt in sorted(sym_counts.items()):
        nc = note_counts.get(bs, 0)
        print('  {:6s}: {:4d} fills, {:3d} with notes  ({:.0%} coverage)'.format(
            bs, cnt, nc, nc/cnt if cnt else 0))

    # Per-symbol note rates (important for bypass decision)
    print()
    print('Per-symbol note rates (determines if ghost filter fires per symbol):')
    for bs, cnt in sorted(sym_counts.items()):
        nc = note_counts.get(bs, 0)
        rate = nc / cnt if cnt else 0
        bypass = rate < 0.25 and cnt > 5
        print('  {:6s}: rate={:.1%}  bypass_would_be={}'.format(bs, rate, bypass))

    # Run ghost classification
    note_rate, bypass = _compute_note_rate(fills)
    fills_sorted = sorted(fills, key=lambda f: (f.ts_val, f.position_order))

    clean_candidates = []
    ghost_fills = []
    for f in fills_sorted:
        if bypass:
            f.suggests_ghost = False
            clean_candidates.append(f)
        else:
            is_ghost = classify_fill(f)
            f.suggests_ghost = is_ghost
            if is_ghost:
                ghost_fills.append(f)
            else:
                clean_candidates.append(f)

    deduped = _dedup_fills(clean_candidates)
    deduped_sorted = sorted(deduped, key=lambda f: (f.ts_val, f.position_order))

    print()
    print('After ghost filter + dedup: {} clean fills ({} ghosts dropped)'.format(
        len(deduped_sorted), len(ghost_fills)))

    # --- Now simulate pair_fills_to_trades() exactly as current code does ---
    # but print every state transition and flag cross-symbol pairings
    print()
    print('FIFO TRACE (current single-queue logic):')
    print('-' * 78)
    header = ('#{:4s}  {:10s} {:6s} {:4s} {:3s} {:10s}  queue_before'
              '  -> queue_after  TRADE?')
    print(header.format('fill', 'ts', 'sym', 'side', 'qty', 'price'))
    print('-' * 78)

    trades = []
    queue = []   # List[_OpenLeg]
    position = 0
    cross_symbol_trades = []

    for idx, f in enumerate(deduped_sorted):
        qty   = f.quantity
        side  = f.side
        delta = +qty if side == 'BUY' else -qty
        new_pos = position + delta
        bs = _base_symbol(f.symbol)

        q_before = [(o.fill.symbol[:6], o.side[:1], o.qty, round(o.price,2)) for o in queue]

        trade_label = ''
        new_trade = None

        # FLIP
        if position != 0 and new_pos != 0 and (position > 0) != (new_pos > 0):
            while queue:
                op = queue.pop(0)
                rt = _make_round_trip(op, f)
                trades.append(rt)
                entry_bs = _base_symbol(op.fill.symbol)
                exit_bs  = _base_symbol(f.symbol)
                cross = entry_bs != exit_bs
                label = 'TRADE(FLIP)' + (' *** CROSS-SYMBOL CONTAMINATION ***' if cross else '')
                trade_label += label + ' entry_sym={} exit_sym={} entry_price={} exit_price={} pnl={:,.2f}'.format(
                    op.fill.symbol, f.symbol, round(op.price,2), round(f.price,2), rt.pnl_dollars)
                if cross:
                    cross_symbol_trades.append({
                        'fill_idx': idx+1,
                        'entry_sym': op.fill.symbol, 'exit_sym': f.symbol,
                        'entry_price': op.price, 'exit_price': f.price,
                        'qty': op.qty, 'pnl': rt.pnl_dollars,
                        'entry_ts': op.time_str, 'exit_ts': f.timestamp,
                    })
            position = 0
            new_contracts = abs(new_pos)
            queue.append(_OpenLeg(fill=f, side=side, qty=new_contracts,
                                  price=f.price, time_str=f.timestamp))
            position = new_pos

        # EXIT / SCALE-OUT
        elif position != 0 and abs(new_pos) < abs(position) and (
            new_pos == 0 or (position > 0) == (new_pos > 0)
        ):
            to_close = abs(position) - abs(new_pos)
            while to_close > 0 and queue:
                op = queue[0]
                entry_bs = _base_symbol(op.fill.symbol)
                exit_bs  = _base_symbol(f.symbol)
                cross = entry_bs != exit_bs
                if op.qty <= to_close:
                    to_close -= op.qty
                    queue.pop(0)
                    rt = _make_round_trip(op, f)
                    trades.append(rt)
                else:
                    from trading_platform.services.ghost_fill_engine import _OpenLeg as _OL
                    partial = _OL(fill=op.fill, side=op.side,
                                  qty=to_close, price=op.price,
                                  time_str=op.time_str)
                    op.qty -= to_close
                    to_close = 0
                    rt = _make_round_trip(partial, f)
                    trades.append(rt)
                label = 'TRADE(EXIT)' + (' *** CROSS-SYMBOL CONTAMINATION ***' if cross else '')
                trade_label += label + ' entry_sym={} exit_sym={} ep={} xp={} pnl={:,.2f}\n         '.format(
                    op.fill.symbol, f.symbol, round(op.price,2), round(f.price,2), rt.pnl_dollars)
                if cross:
                    cross_symbol_trades.append({
                        'fill_idx': idx+1,
                        'entry_sym': op.fill.symbol, 'exit_sym': f.symbol,
                        'entry_price': op.price, 'exit_price': f.price,
                        'qty': min(op.qty+to_close, rt.quantity), 'pnl': rt.pnl_dollars,
                        'entry_ts': op.time_str, 'exit_ts': f.timestamp,
                    })
            position = new_pos

        # ENTRY / SCALE-IN
        elif new_pos != 0 and (position == 0 or abs(new_pos) > abs(position)):
            new_contracts = abs(new_pos) - abs(position)
            queue.append(_OpenLeg(fill=f, side=side, qty=new_contracts,
                                  price=f.price, time_str=f.timestamp))
            position = new_pos
            trade_label = 'ENTRY pos={}'.format(position)

        # NO-OP
        else:
            position = new_pos
            trade_label = 'NOOP'

        q_after = [(o.fill.symbol[:6], o.side[:1], o.qty, round(o.price,2)) for o in queue]

        # Only print lines where something interesting happens
        if trade_label or q_before != q_after or 'CROSS' in trade_label:
            ts_short = str(round(f.ts_val, 1))
            print('#{:4d}  {:12s} {:6s} {:4s} {:3d} {:10.2f}  q={} -> q={}'.format(
                idx+1, ts_short, f.symbol[:8], side, qty, f.price,
                str(q_before)[:35], str(q_after)[:35]))
            if trade_label.strip():
                for line in trade_label.strip().split('\n'):
                    print('         ' + line)

    print()
    print(SEP)
    print('SUMMARY: {} cross-symbol contaminated trades found'.format(len(cross_symbol_trades)))
    print(SEP)
    for i, ct in enumerate(cross_symbol_trades, 1):
        print('  #{}: entry_sym={:10s} exit_sym={:8s}  entry_price={:>12,.2f}  exit_price={:>8,.2f}'.format(
            i, ct['entry_sym'], ct['exit_sym'], ct['entry_price'], ct['exit_price']))
        print('      qty={}  PnL_dollars={:>20,.2f}'.format(ct['qty'], ct['pnl']))
        print('      entry_ts={}  exit_ts={}'.format(ct['entry_ts'][:19], ct['exit_ts'][:19]))
        print()

    print('Total trades produced by current buggy code:', len(trades))
    print()
    return cross_symbol_trades

all_cross = []
for fp in TARGET_FILES:
    if os.path.exists(fp):
        result = trace_file(fp)
        all_cross.extend(result)
    else:
        print('NOT FOUND:', fp)

print()
print(SEP)
print('GRAND TOTAL cross-symbol contaminated trades across all traced files:', len(all_cross))
print(SEP)
print()
print('CONCLUSION:')
if all_cross:
    print('  HYPOTHESIS CONFIRMED: cross-symbol contamination is real.')
    print('  Fix: group fills by base_symbol before Stage 4 (FIFO pairing).')
else:
    print('  No contamination found in traced files.')
    print('  Hypothesis may need revision -- check different files or mechanism.')
