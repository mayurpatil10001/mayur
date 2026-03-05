import os
import sys
import struct
import datetime

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

print(f"Scanning binary contents of {target_fp} for Buy/Buy sequences in V_SIM16...")
fills, ghost_map = _parse_file_nitro(target_fp)

# Filter for V_SIM16
v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']
v_fills.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

print(f"Total V_SIM16 fills in this file: {len(v_fills)}")

current_pos = 0
limit = 3

for i in range(len(v_fills)):
    f = v_fills[i]
    ts = f['timestamp']
    side = f['side']
    qty = f['quantity']
    note = f.get('note', '')
    
    pre_pos = current_pos
    
    # Simple drift projection
    if side == 'BUY':
        current_pos += qty
    else:
        current_pos -= qty
        
    if abs(current_pos) > limit:
        # We found a sequence that crosses the limit
        print(f"\n--- LIMIT EXCEEDED ---")
        # Print a few preceding fills for context
        start = max(0, i - 2)
        end = min(len(v_fills), i + 2)
        for j in range(start, end):
            fj = v_fills[j]
            marker = ">> " if j == i else "   "
            print(f"{marker}[{fj['timestamp']}] {fj['side']} Qty:{fj['quantity']} | Note: '{fj.get('note','')}'")
        
        # Reset current_pos to capped value to stay in sync with my previous explanation
        if current_pos > limit: current_pos = limit
        if current_pos < -limit: current_pos = -limit
        
        # Stop after first few examples to not flood the terminal
        if i > 100: break
