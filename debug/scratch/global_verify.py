import os
import sys
import glob
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, NY_TZ

# Find ALL V_SIM16 files, process them chronologically
log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

print(f"Found {len(files)} V_SIM16 files")

all_fills = []
total_ghosts = 0

for fp in files:
    fills, ghost_map = _parse_file_nitro(fp)
    v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']
    gc = ghost_map.get('V_SIM16', 0)
    total_ghosts += gc
    all_fills.extend(v_fills)

# Sort ALL fills chronologically
all_fills.sort(key=lambda x: x.get('ts_val', 0))

print(f"Total fills across all files: {len(all_fills)}")
print(f"Total ghosts removed: {total_ghosts}")

# FIFO match across ALL fills
buys, sells = [], []
max_long = 0
max_short = 0
violations = 0
first_violation = None

for f in all_fills:
    side = f['side']
    qty = f['quantity']
    
    if side == 'BUY':
        while qty > 0 and sells:
            s = sells[0]
            m = min(qty, s['qty'])
            qty -= m; s['qty'] -= m
            if s['qty'] <= 0: sells.pop(0)
        if qty > 0: buys.append({'qty': qty, 'time': f['timestamp']})
    else:
        while qty > 0 and buys:
            b = buys[0]
            m = min(qty, b['qty'])
            qty -= m; b['qty'] -= m
            if b['qty'] <= 0: buys.pop(0)
        if qty > 0: sells.append({'qty': qty, 'time': f['timestamp']})
    
    open_l = sum(b['qty'] for b in buys)
    open_s = sum(s['qty'] for s in sells)
    
    max_long = max(max_long, open_l)
    max_short = max(max_short, open_s)
    
    if open_l > 3 or open_s > 3:
        violations += 1
        if not first_violation:
            first_violation = f"First violation: {f['timestamp']} | {side} Qty:{f['quantity']} | OpenL:{open_l} OpenS:{open_s}"

print(f"\nRESULTS (All files combined, ghosts removed, FIFO matched):")
print(f"Max Open Long: {max_long}")
print(f"Max Open Short: {max_short}")
print(f"Violations (open > 3): {violations}")
if first_violation:
    print(f"\n{first_violation}")
else:
    print(f"\n*** NO VIOLATIONS! Ghost removal is sufficient. ***")
