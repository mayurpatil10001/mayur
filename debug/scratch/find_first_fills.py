import os
import sys
import glob

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

# Find first file with actual fills
for fp in files:
    fills, gm = _parse_file_nitro(fp)
    v = [f for f in fills if f['account_name'] == 'V_SIM16']
    if len(v) > 0:
        print(f"First file with fills: {os.path.basename(fp)} ({len(v)} fills, ghosts: {gm})")
        
        # FIFO trace first 30
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
            note = f.get('note', '')[:20]
            print(f"  {i+1:3}: {f['timestamp'][:23]} | {side:5} Qty:{f['quantity']} | L:{ol} S:{os_} | {note}{flag}")
        break
