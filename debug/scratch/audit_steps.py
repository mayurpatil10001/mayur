import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone

def audit_vsim16_step_by_step():
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
    fills, ghost_counts = _parse_file_nitro(path)
    
    print(f"Total Fills found: {len(fills)}")
    
    current_net = 0
    limit = 3
    
    for i, f in enumerate(fills[:200]):
        ts = f['timestamp']
        side = f['side']
        qty = f['quantity']
        
        pre = current_net
        intended = (pre + qty) if side == 'BUY' else (pre - qty)
        
        allowed = qty
        rej = 0
        
        if side == 'BUY':
            if intended > limit:
                allowed = max(0, limit - pre)
                rej = qty - allowed
        else: # SELL
            if intended < -limit:
                allowed = max(0, limit + pre)
                rej = qty - allowed
        
        current_net = (pre + allowed) if side == 'BUY' else (pre - allowed)
        
        if rej > 0 or True: # Print all for audit
            rej_str = f" [REJECTED {rej}]" if rej > 0 else ""
            print(f"#{i:03d} [{ts}] {side:<5} {qty:2d} | Pre: {pre:2d} | Allowed: {allowed:2d} | Post: {current_net:2d}{rej_str}")
            if i > 100 and rej == 0: continue # Stop after some rejections start

if __name__ == "__main__":
    audit_vsim16_step_by_step()
