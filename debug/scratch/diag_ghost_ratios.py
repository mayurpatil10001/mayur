import os
import glob
from trading_platform.services.binary_log_parser import _parse_file_nitro

log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

total_fills = 0
total_ghosts = 0
total_valids = 0
valid_buys = 0
valid_sells = 0

for file in files:
    fills, _ = _parse_file_nitro(file)
    total_fills += len(fills)
    
    for f in fills:
        if f.get('is_ghost', False):
            total_ghosts += 1
            if f.get('side') == 'BUY' and '2025-12-18T07:26' in f.get('timestamp', ''):
                print(f"FOUND GHOST MATCH on 12/18: {f}")
        else:
            total_valids += 1
            if f.get('side') == 'BUY':
                valid_buys += 1
            elif f.get('side') == 'SELL':
                valid_sells += 1
            
            if f.get('side') == 'BUY' and '2025-12-18T07:26' in f.get('timestamp', ''):
                print(f"FOUND VALID MATCH on 12/18: {f}")

print(f"\n--- SCAN COMPLETE ---")
print(f"Total Fills: {total_fills}")
print(f"Ghosts: {total_ghosts} | Valids: {total_valids}")
print(f"Valid BUYs: {valid_buys} | Valid SELLs: {valid_sells}")
