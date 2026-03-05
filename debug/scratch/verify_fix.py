import sys, os, datetime, glob
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_file_nitro
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

PATHS = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
]

def get_target_files(paths):
    target_files = []
    dates = ["2025-12-17", "2025-12-18"]
    for p in paths:
        if not os.path.isdir(p): continue
        for d in dates:
             files = glob.glob(os.path.join(p, f"TradeActivityLog_{d}_UTC.V_sim16.data"))
             target_files.extend(files)
    return sorted(list(set(target_files)))

files = get_target_files(PATHS)
all_fills = []
for fp in files:
    fills, ghosts = _parse_file_nitro(fp, ["V_SIM16"])
    all_fills.extend(fills)

# Global Dedup (the fix)
seen_global_keys = set()
global_deduped = []
for fill in all_fills:
    gkey = (
        round(fill.get('ts_val', 0) / 2) * 2,
        fill.get('price'),
        fill.get('side'),
        fill.get('quantity'),
        fill.get('account_name'),
        fill.get('symbol')
    )
    if gkey not in seen_global_keys:
        global_deduped.append(fill)
        seen_global_keys.add(gkey)

global_deduped.sort(key=lambda x: x.get('ts_val', 0))

print(f"Tracing Dec 18 (starting from {files[0]})")
net = 0
for i, f in enumerate(global_deduped):
    ts = f.get('timestamp','')
    try:
        dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        
        # We start tracing net from Dec 17 18:00 NY (the session start for Dec 18)
        # BUT we only want to show it if it matches the Dec 18 session.
        if dt.month == 12 and dt.day == 17 and dt.hour < 18:
            # Continue tracking net but don't print yet
            side = f.get('side','')
            qty = f.get('quantity', 0)
            if side == 'BUY': net += qty
            else: net -= qty
            continue
            
        side = f.get('side','')
        qty = f.get('quantity', 0)
        px = f.get('price', 0)
        if side == 'BUY': net += qty
        else: net -= qty
        
        # Only print from Dec 17 18:00 NY onwards
        if dt.month == 12:
            if dt.day == 17 and dt.hour < 18: continue
            
            # Show net position
            time_str = dt.strftime('%m/%d %H:%M:%S')
            
            # Highlight 02:26 and other key times
            is_target = (dt.hour == 2 and 26 <= dt.minute <= 27)
            if is_target or True: # Show all to be sure
                print(f"{'--> ' if is_target else '    '}{i:3d} | {time_str} | {side:5s} {qty:2d} | net→{net:+d} | {px:8} | note: {f.get('note','')[:35]}")
                
        # Stop after a reasonable amount to avoid too much output
        if dt.month == 12 and dt.day == 18 and dt.hour == 5:
             break
    except: pass
