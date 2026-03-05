import sys
from pathlib import Path
sys.path.insert(0, 'C:/SierraChart/SC results WF')

from trading_platform.services.binary_log_parser import BinaryLogParser, _get_base_symbol_standalone, SYMBOL_METADATA
from tests.test_binary_benchmark_1218 import _load_binary_fills_for_ny_1218

def simulate_pairing():
    fills_all = _load_binary_fills_for_ny_1218(use_trans_time=False, include_ghost=True)
    
    # We need to preserve position_after since we'll use it for sync
    # Let's write the proposed logic
    groups = {}
    for f in fills_all:
        key = (f['account_name'], f['symbol'])
        groups.setdefault(key, []).append(f)
        
    for (acc, specific_sym), group in groups.items():
        group.sort(key=lambda x: (x.get('_position_order', 999999), x.get('ts_val', 0)))
        
        running_position = 0
        open_legs = []
        all_trades = []
        
        print(f"--- ACCOUNT {acc} SYMBOL {specific_sym} ---")
        
        for f in group:
            if f.get('suggests_ghost', False):
                # Optionally skip explicitly flagged ghosts
                # But wait, does skipping them hide the SC state?
                print(f"SKIPPED GHOST: {f['timestamp']} {f['side']} {f['quantity']}")
                continue
                
            side = f['side']
            qty = f['quantity']
            price = f['price']
            ts = f['timestamp']
            pos_after = f.get('position_after')
            
            # --- SYNC LOGIC ---
            if pos_after is not None:
                # Calculate what SC thought the position was BEFORE this fill
                sc_pos_before = pos_after - qty if side == 'BUY' else pos_after + qty
                
                if sc_pos_before != running_position:
                    print(f"[{ts}] DESYNC: Our Pos={running_position}, SC Pre-Pos={sc_pos_before}. Reconciling!")
                    if sc_pos_before == 0:
                        # Flush all open legs (they are ghost trades / noise)
                        print(f"  -> Discarding ghost open legs: {open_legs}")
                        open_legs = []
                        running_position = 0
                    else:
                        print(f"  -> SC Pre-Pos = {sc_pos_before}. Don't know how to handle partial desync yet.")

            prev_pos = running_position
            if side == 'BUY': running_position += qty
            else: running_position -= qty
            
            if abs(running_position) > abs(prev_pos):
                open_legs.append({"qty": qty, "price": price, "time": ts, "side": side})
                print(f"[{ts}] OPEN {side} {qty} at {price}. Pos: {running_position}")
            else:
                rem_qty = qty
                while rem_qty > 0 and open_legs:
                    match_idx = -1
                    for i, leg in enumerate(open_legs):
                        if leg['side'] != side:
                            match_idx = i
                            break
                    if match_idx == -1: break
                    
                    leg = open_legs[match_idx]
                    take = min(rem_qty, leg['qty'])
                    
                    print(f"[{ts}] CLOSE {side} {take} at {price}. Closes front leg of {leg['side']} at {leg['price']}.")
                    
                    leg['qty'] -= take
                    rem_qty -= take
                    if leg['qty'] <= 0:
                        open_legs.pop(match_idx)
                        
                if rem_qty > 0:
                    open_legs.append({"qty": rem_qty, "price": price, "time": ts, "side": side})
                    print(f"[{ts}] OPEN (FLIP) {side} {rem_qty} at {price}. Pos: {running_position}")

if __name__ == '__main__':
    simulate_pairing()

