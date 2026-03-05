"""
Check pending_fills table for V_SIM16 and trace the cross-file boundary issue.
Also check the Dec 17 UTC file to see what carryover SHORT positions exist.
"""
import sys, os, sqlite3, datetime
sys.path.insert(0, r"C:\SierraChart\SC results WF")
os.chdir(r"C:\SierraChart\SC results WF")

from zoneinfo import ZoneInfo
NY_TZ = ZoneInfo("America/New_York")
DB = r"C:\SierraChart\SC results WF\trading_platform.db"

conn = sqlite3.connect(DB)
c = conn.cursor()

# Check pending_fills for V_SIM16
print("=== PENDING FILLS for V_SIM16 ===")
try:
    c.execute("""
        SELECT account_name, symbol, side, entry_time, price, quantity, created_at
        FROM pending_fills
        WHERE account_name = 'V_SIM16'
        ORDER BY entry_time
    """)
    rows = c.fetchall()
    print(f"Count: {len(rows)}")
    for r in rows:
        print(f"  {r[2]:5s} qty={r[4]} @ {r[3]} px={r[3]}")
except Exception as e:
    print(f"Error: {e}")

conn.close()

# Now parse the Dec 17 UTC file to see what fills are there
print("\n=== Parsing Dec 17 UTC file for V_SIM16 ===")
from trading_platform.services.binary_log_parser import _parse_file_nitro

DEC17_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-17_UTC.V_sim16.data"
DEC18_FILE = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

import os
if os.path.exists(DEC17_FILE):
    fills17, ghosts17 = _parse_file_nitro(DEC17_FILE)
    print(f"Dec 17 UTC file: {len(fills17)} fills, {len(ghosts17)} ghosts")
    
    # Net position at END of Dec 17 file (19:00 NY = the handoff point to Dec 18)
    fills17.sort(key=lambda x: x.get("ts_val", 0))
    
    net = 0
    buy_total = 0
    sell_total = 0
    for f in fills17:
        side = f.get("side", "")
        qty = f.get("quantity", 0)
        if side == "BUY":
            net += qty
            buy_total += qty
        else:
            net -= qty
            sell_total += qty
    
    print(f"Dec 17 UTC file net position at end: {net:+d} (buy_total={buy_total}, sell_total={sell_total})")
    print(f"(Positive = net LONG, Negative = net SHORT)")
    
    # Show the last 10 fills in Dec 17 to understand what's open
    print(f"\nLast 10 fills in Dec 17 UTC file:")
    for f in fills17[-10:]:
        ts = f.get("timestamp", "")
        try:
            dt = datetime.datetime.fromisoformat(ts).replace(tzinfo=datetime.timezone.utc).astimezone(NY_TZ)
            print(f"  {dt.strftime('%m/%d %H:%M:%S')} | {f.get('side',''):5s} {f.get('quantity',0)} @ {f.get('price',0)} | note: {f.get('note','')[:25]}")
        except:
            print(f"  {ts} | {f.get('side','')} {f.get('quantity',0)}")
else:
    print(f"File NOT FOUND: {DEC17_FILE}")
    # Search for it
    import glob
    found = glob.glob(r"D:\SierraChart_Simulated_Feed\**\*2025-12-17*V_sim16*", recursive=True)
    print(f"Searching... found: {found}")
