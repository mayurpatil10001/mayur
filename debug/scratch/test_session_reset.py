import os
import sys
import glob
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, NY_TZ

log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
files = sorted(glob.glob(os.path.join(log_dir, "TradeActivityLog_*_UTC.V_sim16.data")))

# Grab 10 consecutive files with fills
test_files = []
for fp in files:
    fills, gm = _parse_file_nitro(fp)
    v = [f for f in fills if f['account_name'] == 'V_SIM16']
    if len(v) > 0:
        test_files.append((fp, v))
    if len(test_files) >= 10:
        break

all_fills = []
for fp, v in test_files:
    all_fills.extend(v)
all_fills.sort(key=lambda x: x.get('ts_val', 0))

# Simulate FIFO with session-boundary reset at 17:00 NY
def get_session(ts_str):
    try:
        dt = datetime.datetime.fromisoformat(ts_str)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_ny = dt.astimezone(NY_TZ)
        if dt_ny.hour >= 17: return (dt_ny + datetime.timedelta(days=1)).date()
        return dt_ny.date()
    except: return None

buys, sells = [], []
trades = []
unpaired = 0
last_session = None

for f in all_fills:
    side, qty, price, ts = f['side'], f['quantity'], f['price'], f['timestamp']
    ts_val = f.get('ts_val', 0)
    
    current_session = get_session(ts)
    if last_session is not None and current_session != last_session:
        unpaired += sum(b['qty'] for b in buys) + sum(s['qty'] for s in sells)
        buys, sells = [], []
    last_session = current_session
    
    if side == 'BUY':
        while qty > 0 and sells:
            s = sells[0]
            m = min(qty, s['qty'])
            try:
                dur = (datetime.datetime.fromisoformat(ts) - datetime.datetime.fromisoformat(s['time'])).total_seconds() / 3600
            except: dur = 0
            trades.append({'dur_hrs': dur, 'entry': s['time'], 'exit': ts})
            qty -= m; s['qty'] -= m
            if s['qty'] <= 0: sells.pop(0)
        if qty > 0: buys.append({'qty': qty, 'price': price, 'time': ts, 'ts_val': ts_val})
    else:
        while qty > 0 and buys:
            b = buys[0]
            m = min(qty, b['qty'])
            try:
                dur = (datetime.datetime.fromisoformat(ts) - datetime.datetime.fromisoformat(b['time'])).total_seconds() / 3600
            except: dur = 0
            trades.append({'dur_hrs': dur, 'entry': b['time'], 'exit': ts})
            qty -= m; b['qty'] -= m
            if b['qty'] <= 0: buys.pop(0)
        if qty > 0: sells.append({'qty': qty, 'price': price, 'time': ts, 'ts_val': ts_val})

# Final flush
unpaired += sum(b['qty'] for b in buys) + sum(s['qty'] for s in sells)

ok = [t for t in trades if t['dur_hrs'] <= 24]
bad = [t for t in trades if t['dur_hrs'] > 24]
print(f"Total trades: {len(trades)}")
print(f"  OK (<24h): {len(ok)}")
print(f"  BAD (>24h): {len(bad)}")
print(f"  Unpaired fills: {unpaired}")
if bad:
    print(f"\nBad trades:")
    for t in bad[:5]:
        print(f"  Entry: {t['entry'][:23]} -> Exit: {t['exit'][:23]} | {t['dur_hrs']:.1f}h")

# Max duration
if trades:
    max_dur = max(t['dur_hrs'] for t in trades)
    print(f"\nMax trade duration: {max_dur:.1f} hours")
