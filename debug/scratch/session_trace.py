import os
import sys
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills_clean, _ = _parse_file_nitro(target_fp)
v_clean = [f for f in fills_clean if f['account_name'] == 'V_SIM16']
v_clean.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# The user's screenshot shows fills starting at 02:12 NY time on Dec 18
# which is 07:12 UTC
# My parser shows fills starting at 00:01 UTC = 19:01 NY Dec 17
# These early fills are from the PREVIOUS session's tail

# Let me trace ONLY the fills that match the user's view (starting from ~07:00 UTC = 02:00 NY)
# which is the Dec 18 NY session

print("=== POSITION TRACE MATCHING USER'S SCREENSHOT (Starting 07:00 UTC / 02:00 NY) ===")
print()

net_pos = 0
exceed_count = 0

# But first - this is a day file. What was the position BEFORE 07:00 UTC?
# The fills before 07:00 UTC could leave a non-zero position
early_fills = [f for f in v_clean if f.get('ts_val', 0) < 1734508800]  # approx 07:00 UTC Dec 18
late_fills = [f for f in v_clean if f.get('ts_val', 0) >= 1734508800]

# Calculate carryover
for f in early_fills:
    if f['side'] == 'BUY': net_pos += f['quantity']
    else: net_pos -= f['quantity']
print(f"Early fills (before 07:00 UTC / 02:00 NY): {len(early_fills)} fills")
print(f"Carryover net position: {net_pos}")
print()

# Now trace the late fills
print(f"{'#':3} | {'Timestamp':25} | {'NYapprox':10} | {'Side':5} | {'Qty':3} | {'PrePos':6} | {'PostPos':7} | {'OID':12} | Status")
print("-" * 120)

for i, f in enumerate(late_fills):
    side = f['side']
    qty = f['quantity']
    ts = f['timestamp']
    oid = str(f.get('order_id') or 'N/A')
    
    pre = net_pos
    if side == 'BUY': net_pos += qty
    else: net_pos -= qty
    
    flag = f"OVER! net={net_pos}" if abs(net_pos) > 3 else "OK"
    if abs(net_pos) > 3: exceed_count += 1
    
    # Approximate NY time (UTC - 5)
    import datetime
    try:
        dt_utc = datetime.datetime.fromisoformat(ts)
        dt_ny = dt_utc - datetime.timedelta(hours=5)
        ny_str = dt_ny.strftime("%H:%M:%S")
    except:
        ny_str = "???"
    
    print(f"{i+1:3} | {ts[:23]:25} | {ny_str:10} | {side:5} | {qty:3} | {pre:6} | {net_pos:7} | {oid:12} | {flag}")

print(f"\nTotal late fills: {len(late_fills)}")
print(f"Exceeds: {exceed_count}")
