"""Phase 0 + 1 investigation: extract raw fills for Jun-23 and Jul-02 IPS_TM_7 NQ."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from trading_platform.services.binary_log_parser import _parse_file_nitro
from trading_platform.services.ghost_fill_engine import (
    FillRecord, GhostFillEngine, classify_fill, pair_fills_to_trades, _has_strategy_tag
)

CASES = [
    ('2026-06-23', 'dataset/TradeActivityLog_2026-06-23_UTC.IPS_TM_7.data'),
    ('2026-07-02', 'dataset/TradeActivityLog_2026-07-02_UTC.IPS_TM_7.data'),
]

for date, fp in CASES:
    print(f"\n{'='*80}")
    print(f"DATE: {date}  FILE: {fp}")
    print(f"{'='*80}")

    raw, _ = _parse_file_nitro(fp)
    nq_raw = [f for f in raw if 'NQ' in str(f.get('symbol', ''))]
    print(f"Total NQ fills in file: {len(nq_raw)}")

    # Show every fill with all fields needed for ground truth
    print(f"\n{'IDX':>3} | {'TIMESTAMP':>19} | {'SIDE':>4} | {'QTY':>4} | {'PRICE':>10} | {'OC':>5} | {'TE?':>3} | {'NOTE_LEN':>8} | {'NOTE/MSG_SNIPPET'}")
    print("-"*120)
    fills = GhostFillEngine.from_dicts(nq_raw)
    for i, f in enumerate(fills):
        is_te = 'trading evaluator' in f.msgtxt.lower()
        is_ghost = f.suggests_ghost or classify_fill(f)
        note_snippet = (f.note or '').strip()[:20]
        msg_snippet  = (f.msgtxt or '').strip()[:30]
        print(f"{i:>3} | {f.timestamp[:19]:>19} | {f.side:>4} | {f.quantity:>4} | {f.price:>10.2f} | {f.open_close:>5} | {'YES' if is_te else 'no':>3} | {'GHOST' if is_ghost else 'real':>8} | note={repr(note_snippet)} msg={repr(msg_snippet)}")

    print(f"\n--- GHOST FILL DETAILS (classified ghost=True) ---")
    ghost_count = 0
    for i, f in enumerate(fills):
        is_ghost = f.suggests_ghost or classify_fill(f)
        if is_ghost:
            ghost_count += 1
            print(f"  IDX={i} | ts={f.timestamp} | {f.side} {f.quantity}x @ {f.price:.2f}")
            print(f"    note: {repr(f.note)}")
            print(f"    msgtxt: {repr(f.msgtxt[:120])}")
            print(f"    open_close={f.open_close} | position_order={f.position_order}")
    print(f"Total ghosts classified: {ghost_count}")

    print(f"\n--- DIRTY FIFO PAIRING (all fills) ---")
    all_fills = list(fills)
    for g in all_fills:
        g.suggests_ghost = False  # force all as non-ghost
    dirty_trades, dirty_unpaired = pair_fills_to_trades(all_fills)
    dirty_net = sum(t.pnl_dollars for t in dirty_trades)
    dirty_wins = sum(1 for t in dirty_trades if t.pnl_dollars > 0)
    print(f"  Trades: {len(dirty_trades)} | Wins: {dirty_wins} | Net: ${dirty_net:,.2f}")
    for t in dirty_trades:
        sign = '+' if t.pnl_dollars >= 0 else ''
        print(f"    {t.direction:5} {t.quantity}x @ entry={t.entry_price:.2f} exit={t.exit_price:.2f} | {t.entry_time[:19]} -> {t.exit_time[:19]} | {sign}${t.pnl_dollars:,.2f}")

    print(f"\n--- CLEAN FIFO PAIRING (ghost fills removed) ---")
    clean_fills = GhostFillEngine.from_dicts(nq_raw)
    clean_fills_filtered = [f for f in clean_fills if not classify_fill(f)]
    clean_trades, clean_unpaired = pair_fills_to_trades(clean_fills_filtered)
    clean_net = sum(t.pnl_dollars for t in clean_trades)
    clean_wins = sum(1 for t in clean_trades if t.pnl_dollars > 0)
    print(f"  Trades: {len(clean_trades)} | Wins: {clean_wins} | Net: ${clean_net:,.2f}")
    for t in clean_trades:
        sign = '+' if t.pnl_dollars >= 0 else ''
        print(f"    {t.direction:5} {t.quantity}x @ entry={t.entry_price:.2f} exit={t.exit_price:.2f} | {t.entry_time[:19]} -> {t.exit_time[:19]} | {sign}${t.pnl_dollars:,.2f}")

    print(f"\n--- DELTA SUMMARY ---")
    print(f"  Dirty Net: ${dirty_net:,.2f}  |  Clean Net: ${clean_net:,.2f}  |  Delta: ${clean_net-dirty_net:+,.2f}")
    print(f"  Fills removed as ghost: {len(fills) - len(clean_fills_filtered)}")
