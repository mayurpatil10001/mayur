import os
import sys
import glob
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, NY_TZ

# Parse just a few consecutive V_SIM16 files and trace FIFO
log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

# Take 5 consecutive files with fills
test_files = []
for fp in files:
    fills, gm = _parse_file_nitro(fp)
    v = [f for f in fills if f['account_name'] == 'V_SIM16']
    if len(v) > 0:
        test_files.append((fp, v, gm))
    if len(test_files) >= 5:
        break

print(f"Testing {len(test_files)} files:")
for fp, v, gm in test_files:
    print(f"  {os.path.basename(fp)}: {len(v)} fills, ghosts: {gm}")

# Combine all fills and do FIFO
all_fills = []
for fp, v, gm in test_files:
    all_fills.extend(v)

all_fills.sort(key=lambda x: x.get('ts_val', 0))

# FIFO and check how many trades would be >24h
buys, sells = [], []
trades = []
for f in all_fills:
    side = f['side']
    qty = f['quantity']
    ts = f['timestamp']
    ts_val = f.get('ts_val', 0)
    price = f['price']
    
    if side == 'BUY':
        while qty > 0 and sells:
            s = sells[0]
            m = min(qty, s['qty'])
            # Check duration
            try:
                entry_dt = datetime.datetime.fromisoformat(s['time'])
                exit_dt = datetime.datetime.fromisoformat(ts)
                dur_hrs = (exit_dt - entry_dt).total_seconds() / 3600
            except:
                dur_hrs = 0
            trades.append({'entry': s['time'], 'exit': ts, 'dur_hrs': dur_hrs, 'side': 'SHORT'})
            qty -= m; s['qty'] -= m
            if s['qty'] <= 0: sells.pop(0)
        if qty > 0: buys.append({'qty': qty, 'price': price, 'time': ts, 'ts_val': ts_val})
    else:
        while qty > 0 and buys:
            b = buys[0]
            m = min(qty, b['qty'])
            try:
                entry_dt = datetime.datetime.fromisoformat(b['time'])
                exit_dt = datetime.datetime.fromisoformat(ts)
                dur_hrs = (exit_dt - entry_dt).total_seconds() / 3600
            except:
                dur_hrs = 0
            trades.append({'entry': b['time'], 'exit': ts, 'dur_hrs': dur_hrs, 'side': 'LONG'})
            qty -= m; b['qty'] -= m
            if b['qty'] <= 0: buys.pop(0)
        if qty > 0: sells.append({'qty': qty, 'price': price, 'time': ts, 'ts_val': ts_val})

# Stats
ok_trades = [t for t in trades if t['dur_hrs'] <= 24]
bad_trades = [t for t in trades if t['dur_hrs'] > 24]
print(f"\nTotal trades created: {len(trades)}")
print(f"  OK (<24h): {len(ok_trades)}")
print(f"  BAD (>24h): {len(bad_trades)}")

# Show first few bad trades
if bad_trades:
    print(f"\nFirst 5 bad trades (>24h):")
    for t in bad_trades[:5]:
        print(f"  {t['side']:6} Entry: {t['entry'][:23]} -> Exit: {t['exit'][:23]} | Duration: {t['dur_hrs']:.1f}h")

# Check end-of-day balance per file
print(f"\nEnd-of-file FIFO balance:")
for fp, v, gm in test_files:
    buys2, sells2 = [], []
    for f in v:
        qty = f['quantity']
        if f['side'] == 'BUY':
            while qty > 0 and sells2:
                s = sells2[0]
                m = min(qty, s['qty'])
                qty -= m; s['qty'] -= m
                if s['qty'] <= 0: sells2.pop(0)
            if qty > 0: buys2.append({'qty': qty})
        else:
            while qty > 0 and buys2:
                b = buys2[0]
                m = min(qty, b['qty'])
                qty -= m; b['qty'] -= m
                if b['qty'] <= 0: buys2.pop(0)
            if qty > 0: sells2.append({'qty': qty})
    
    ol = sum(b['qty'] for b in buys2)
    os_ = sum(s['qty'] for s in sells2)
    print(f"  {os.path.basename(fp)}: Unpaired Buys={ol}, Unpaired Sells={os_}")
