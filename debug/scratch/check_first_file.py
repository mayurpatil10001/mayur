import os
import sys
import glob
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, NY_TZ

# Parse ONLY the first file to check
log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

print(f"First file: {files[0]}")
fills, ghost_map = _parse_file_nitro(files[0])
v = [f for f in fills if f['account_name'] == 'V_SIM16']
v.sort(key=lambda x: x.get('ts_val', 0))
print(f"Fills: {len(v)}, Ghosts removed: {ghost_map}")

# FIFO first 30 fills
buys, sells = [], []
for i, f in enumerate(v[:30]):
    side = f['side']
    qty = f['quantity']
    if side == 'BUY':
        while qty > 0 and sells:
            s = sells[0]
            m = min(qty, s['qty'])
            qty -= m; s['qty'] -= m
            if s['qty'] <= 0: sells.pop(0)
        if qty > 0: buys.append({'qty': qty})
    else:
        while qty > 0 and buys:
            b = buys[0]
            m = min(qty, b['qty'])
            qty -= m; b['qty'] -= m
            if b['qty'] <= 0: buys.pop(0)
        if qty > 0: sells.append({'qty': qty})
    
    ol = sum(b['qty'] for b in buys)
    os_ = sum(s['qty'] for s in sells)
    flag = " !!!" if ol > 3 or os_ > 3 else ""
    ts = f['timestamp'][:23]
    note = f.get('note', '')[:20]
    print(f"  {i+1:3}: {ts} | {side:5} Qty:{f['quantity']} | L:{ol} S:{os_} | Note:{note}{flag}")
