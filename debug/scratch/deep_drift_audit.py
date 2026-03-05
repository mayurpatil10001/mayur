import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone

async def deep_drift_audit():
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    # Process just one file to be fast and detailed
    file = os.path.join(path, "TradeActivityLog_2026-02-25_UTC.V_sim16.data")
    
    fills, ghost_counts = _parse_file_nitro(file)
    print(f"File processed. Total fills: {len(fills)}")
    
    groups = {}
    for f in fills:
        key = (f['account_name'], f['symbol'])
        if key not in groups: groups[key] = []
        groups[key].append(f)
        
    for (acc, sym), group in groups.items():
        base_sym = _get_base_symbol_standalone(sym)
        group.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))
        
        # Deduplicate (500ms window as in main code)
        deduped = []
        sigs = set()
        for f in group:
            sig = (round(f.get('ts_val', 0) * 2) / 2.0, f['price'], f['side'], f['quantity'])
            if sig not in sigs:
                deduped.append(f)
                sigs.add(sig)
        
        current_net = 0
        limit = 3
        print(f"\n--- AUDIT FOR {acc} {sym} ---")
        for i, f in enumerate(deduped[:100]): # More rows to see the drift
            qty = f['quantity']
            side = f['side']
            ts = f['timestamp']
            
            # Use same logic as binary_log_parser.py
            intended = 0
            rejection = 0
            if side == 'BUY' or side == 'LONG':
                intended = current_net + qty
                if intended > limit:
                   rejection = qty - (limit - current_net)
            else: # SELL or SHORT
                intended = current_net - qty
                if intended < -limit:
                    rejection = qty - (limit + current_net)
            
            allowed = qty - (rejection if rejection > 0 else 0)
            pre = current_net
            if side == 'BUY' or side == 'LONG': current_net += allowed
            else: current_net -= allowed
            
            rej_str = f" [REJECTED {rejection}]" if (rejection if rejection > 0 else 0) > 0 else ""
            print(f"[{ts}] {side:<4} {qty:2d} | Pre: {pre:2d} | Allowed: {allowed:2d} | Post: {current_net:2d}{rej_str}")

if __name__ == "__main__":
    asyncio.run(deep_drift_audit())
