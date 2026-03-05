"""
Diagnose why the 02:26 BUY 3 duplicate escaped the PRE-DEDUP.
Check the actual ts_val values for the two copies.
"""
import sys, os
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_file_nitro
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")
LOG_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
fills, ghosts = _parse_file_nitro(LOG_FILE)
fills.sort(key=lambda x: x.get("ts_val", 0))

# Find all BUY fills at 02:26
print("=== 02:26 BUY fills (detailed ts_val) ===")
for f in fills:
    ts = f.get("timestamp","")
    if not ts: continue
    try:
        dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        if dt.hour == 2 and dt.minute == 26 and f.get("side") == "BUY":
            tv = f.get("ts_val", 0)
            rounded = round(tv * 2) / 2.0
            print(f"  ts={ts}")
            print(f"  ts_val={tv:.6f}  rounded_500ms={rounded}")
            print(f"  price={f.get('price')} qty={f.get('quantity')} note={f.get('note','')[:40]}")
            print(f"  dedup_key=({rounded}, {f.get('price')}, {f.get('side')}, {f.get('quantity')})")
            print()
    except: pass
