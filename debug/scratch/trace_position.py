"""
Trace full FIFO fill sequence for V_SIM16 Dec 18 to understand
why the 02:26 BUY is being consumed by SHORT close instead of opening a LONG.
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

fills.sort(key=lambda x: x.get('ts_val', 0))

print(f"Fills after PRE-DEDUP: {len(fills)}")

# Show all fills chronologically, focusing on the zone around 02:26
print("\n=== ALL FILLS AROUND 00:00-04:30 NY ===")
buy_q = 0
sell_q = 0
net = 0  # positive = net long, negative = net short

print(f"{'Time':>10}  {'Side':>5}  {'Qty':>4}  {'Price':>10}  {'Net Pos':>8}  Note")
print("-" * 80)

for f in fills:
    ts = f.get("timestamp", "")
    if not ts:
        continue
    try:
        dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        if not (0 <= dt.hour < 5):
            continue
        side = f.get("side", "")
        qty = f.get("quantity", 0)
        px = f.get("price", 0)
        if side == "BUY":
            net += qty
        else:
            net -= qty
        note = f.get("note", "")[:30]
        time_str = dt.strftime("%H:%M:%S")
        flag = " <-- 02:26 ENTRY" if (dt.hour == 2 and dt.minute == 26) else ""
        flag = " <-- 04:05 GHOST?" if (dt.hour == 4 and dt.minute == 5) and not note else flag
        flag = " <-- 04:18 EXIT" if (dt.hour == 4 and dt.minute == 18) else flag
        print(f"{time_str:>10}  {side:>5}  {qty:>4}  {px:>10}  {net:>+8}  {note}{flag}")
    except:
        pass

print("\nGhosts:")
for g in ghosts:
    ts = g.get("timestamp", "")
    try:
        dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
        print(f"  GHOST: {dt.strftime('%H:%M:%S')} | {g.get('side','')} {g.get('quantity','')} @ {g.get('price','')} | note='{g.get('note','')}'")
    except: pass
