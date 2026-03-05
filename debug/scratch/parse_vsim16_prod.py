"""
Use the actual production parsing logic from binary_log_parser.py
to examine what fills come out of V_SIM16 Dec 18 log,
and diagnose what happens at 02:26 and 04:05.
"""
import sys
import os
sys.path.insert(0, r"C:\SierraChart\SC results WF")

from trading_platform.services.binary_log_parser import _parse_file_nitro
import datetime
from zoneinfo import ZoneInfo

NY_TZ = ZoneInfo("America/New_York")

# Change to working dir so relative paths work
os.chdir(r"C:\SierraChart\SC results WF")

LOG_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

print(f"Parsing: {LOG_FILE}")
fills, ghosts = _parse_file_nitro(LOG_FILE)

print(f"\nFills returned from parser: {len(fills)}")
print(f"Ghosts returned from parser: {len(ghosts)}")

# Note rate check
total_with_notes = sum(1 for f in fills if f.get('note','').strip())
if fills:
    print(f"Fill note rate: {total_with_notes}/{len(fills)} = {total_with_notes/len(fills)*100:.1f}%")

# Show fills in 02:20-02:40 and 04:00-04:25 NY windows
print("\n=== FILLS IN KEY WINDOWS ===")
for f in fills + ghosts:
    label = "FILL" if f in fills else "GHOST"
    ts = f.get('timestamp', '')
    if not ts:
        continue
    try:
        dt = datetime.datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        dt_ny = dt.astimezone(NY_TZ)
        if (dt_ny.hour == 2 and 20 <= dt_ny.minute <= 40) or (dt_ny.hour == 4 and 0 <= dt_ny.minute <= 25):
            note = f.get('note', '')
            print(f"  [{label}] {dt_ny.strftime('%H:%M:%S')} | {f.get('side','')} {f.get('quantity','')} @ {f.get('price','')} | note={'YES:'+note[:30] if note else 'EMPTY'}")
    except:
        pass

# Also show ghosts explicitly
print("\n=== ALL GHOSTS ===")
for g in ghosts:
    ts = g.get('timestamp', '')
    try:
        dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        print(f"  {dt.strftime('%H:%M:%S')} | {g.get('side','')} {g.get('quantity','')} @ {g.get('price','')} | note: '{g.get('note','')}'")
    except:
        print(f"  {ts} | {g}")
