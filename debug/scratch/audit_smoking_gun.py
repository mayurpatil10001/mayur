import sys, os, datetime, glob
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import BinaryLogParser
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

PATHS = [
    r"D:\SierraChart_Simulated_Feed\TradeActivityLogs",
    r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
]

parser = BinaryLogParser()

# Filter files to only look at last 90 days for V_SIM16
def get_recent_files(paths, days=90):
    recent_files = []
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    for p in paths:
        if not os.path.isdir(p): continue
        files = glob.glob(os.path.join(p, "TradeActivityLog_*_UTC.V_sim16.data"))
        for f in files:
            # Extract date from filename
            import re
            m = re.search(r'(\d{4}-\d{2}-\d{2})', os.path.basename(f))
            if m:
                f_date = datetime.datetime.strptime(m.group(1), "%Y-%m-%d")
                if f_date >= cutoff:
                    recent_files.append(f)
    return sorted(list(set(recent_files)))

files = get_recent_files(PATHS, 90)
print(f"Auditing {len(files)} files over last 90 days...")

# Gather fills using the NEW production logic (Global Dedup + Deferred Ghost)
# But we'll do it manually to trace the net position
from trading_platform.services.binary_log_parser import _parse_file_nitro

all_raw_fills = []
for fp in files:
    fills, _ = _parse_file_nitro(fp, ["V_SIM16"])
    all_raw_fills.extend(fills)

# Global Dedup (Exact logic from run_import)
seen_global_keys = {}
global_deduped = []
for f in all_raw_fills:
    ts_val = f.get('ts_val', 0)
    ts_bucket = round(ts_val / 2) * 2
    key = (f.get('account_name'), f.get('symbol'), f.get('side'), f.get('price'), f.get('quantity'), ts_bucket)
    
    if key not in seen_global_keys:
        seen_global_keys[key] = f
    else:
        # Keep version with note
        if seen_global_keys[key].get('suggests_ghost') and not f.get('suggests_ghost'):
            seen_global_keys[key] = f

global_deduped = list(seen_global_keys.values())
global_deduped.sort(key=lambda x: x.get('ts_val', 0))

print("\n--- AUDIT START ---")
net = 0
smoking_gun_found = False

for i, f in enumerate(global_deduped):
    side = f.get('side','')
    qty = f.get('quantity', 0)
    if side == 'BUY': net += qty
    else: net -= qty
    
    # Check if position is NOT divisible by 3 (assuming strategy is 3-lot only)
    # Most strategy trades are in 3s.
    if net % 3 != 0 and not smoking_gun_found:
        ts = f.get('timestamp','')
        print(f"\n*** SMOKING GUN: Position first became non-3-multiple at index {i} ***")
        print(f"Time: {ts}")
        print(f"Fill: {side} {qty:2d} @ {f.get('price')} | Net: {net:+d}")
        print(f"Note: {f.get('note')}")
        smoking_gun_found = True
        # Show surrounding fills
        print("\nSurrounding fills:")
        for j in range(max(0, i-5), min(len(global_deduped), i+6)):
            curr = global_deduped[j]
            prefix = ">>>" if j == i else "   "
            print(f"{prefix} {j:3d} | {curr.get('timestamp')} | {curr.get('side'):5s} {curr.get('quantity'):2d} | Note: {curr.get('note')[:40]}")
        # Stop audit here to analyze
        break

if not smoking_gun_found:
    print("\nAccount stayed balanced in 3-lot increments.")
    print(f"Final net position: {net:+d}")
