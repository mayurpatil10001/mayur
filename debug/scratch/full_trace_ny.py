import os
import sys
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, _to_ny, NY_TZ

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills_clean, _ = _parse_file_nitro(target_fp)
v_clean = [f for f in fills_clean if f['account_name'] == 'V_SIM16']
v_clean.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# The timestamps from parser are naive datetime strings (UTC-based from the filename)
# Let's convert to NY time properly
# The file is "_UTC" so timestamps are UTC

print("=== FULL POSITION TRACE WITH NY TIME ===")
print()

with open("full_pos_trace.txt", "w") as out:
    net_pos = 0
    exceed_count = 0
    
    out.write(f"{'#':3} | {'UTC Time':25} | {'NY Time':10} | {'Side':5} | {'Qty':3} | {'PrePos':6} | {'PostPos':7} | {'OID':12} | Status\n")
    out.write("-" * 120 + "\n")
    
    for i, f in enumerate(v_clean):
        side = f['side']
        qty = f['quantity']
        ts = f['timestamp']
        oid = str(f.get('order_id') or 'N/A')
        
        # Convert to NY time
        try:
            dt_utc = datetime.datetime.fromisoformat(ts).replace(tzinfo=ZoneInfo("UTC"))
            dt_ny = dt_utc.astimezone(NY_TZ)
            ny_str = dt_ny.strftime("%H:%M:%S")
        except:
            ny_str = "???"
        
        pre = net_pos
        if side == 'BUY': net_pos += qty
        else: net_pos -= qty
        
        flag = f"OVER! net={net_pos}" if abs(net_pos) > 3 else "OK"
        if abs(net_pos) > 3: exceed_count += 1
        
        out.write(f"{i+1:3} | {ts[:23]:25} | {ny_str:10} | {side:5} | {qty:3} | {pre:6} | {net_pos:7} | {oid:12} | {flag}\n")
    
    out.write(f"\nTotal fills: {len(v_clean)}\n")
    out.write(f"Exceeds: {exceed_count}\n")

print("Done, check full_pos_trace.txt")
