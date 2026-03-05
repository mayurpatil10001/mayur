import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from trading_platform.services.binary_log_parser import _parse_file_nitro, _get_base_symbol_standalone

def audit_vsim16_notes():
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-25_UTC.V_sim16.data"
    fills, ghost_counts = _parse_file_nitro(path)
    
    print(f"Total Fills found: {len(fills)}")
    print(f"Parsing Ghosts found: {ghost_counts.get('V_SIM16', 0)}")
    
    current_net = 0
    limit = 3
    
    for f in fills[:50]:
        ts = f['timestamp']
        side = f['side']
        qty = f['quantity']
        note = f.get('note', '')
        
        intended = (current_net + qty) if side == 'BUY' else (current_net - qty)
        rej = 0
        if side == 'BUY' and intended > limit: rej = qty - (limit - current_net)
        elif side == 'SELL' and intended < -limit: rej = qty - (limit + current_net)
        
        allowed = qty - (rej if rej > 0 else 0)
        pre = current_net
        if side == 'BUY': current_net += allowed
        else: current_net -= allowed
        
        rej_str = f" [DRIFT {rej}]" if (rej if rej > 0 else 0) > 0 else ""
        print(f"[{ts}] {side:<5} {qty:2d} | Pre: {pre:2d} | Post: {current_net:2d}{rej_str:10} | Note: '{note[:30]}...'")

if __name__ == "__main__":
    audit_vsim16_notes()
