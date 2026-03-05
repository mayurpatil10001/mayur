import os
import sys
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills_clean, ghost_map_clean = _parse_file_nitro(target_fp)

v_clean = [f for f in fills_clean if f['account_name'] == 'V_SIM16']
v_clean.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# Show first 20 fills - write to a file
with open("first20_output.txt", "w") as out:
    net_pos = 0
    out.write("First 20 fills after ghost removal:\n")
    for i, f in enumerate(v_clean[:20]):
        side = f['side']
        qty = f['quantity']
        pre = net_pos
        if side == 'BUY': net_pos += qty
        else: net_pos -= qty
        oid = str(f.get('order_id') or 'N/A')
        note = str(f.get('note', ''))[:25]
        flag = " !!!" if abs(net_pos) > 3 else ""
        out.write(f"  {i+1:3}: {f['timestamp'][:23]} | {side:5} {qty} | Pre:{pre:3} Post:{net_pos:3} | OID:{oid:12} | Note:{note}{flag}\n")
    
    out.write(f"\nTotal fills: {len(v_clean)}\n")
    
    # Count how many fills exceed limit if we just add them up
    net_pos = 0
    exceed_count = 0
    for f in v_clean:
        if f['side'] == 'BUY': net_pos += f['quantity']
        else: net_pos -= f['quantity']
        if abs(net_pos) > 3: exceed_count += 1
    out.write(f"Fills where |pos| > 3 (raw count): {exceed_count}\n")

print("Done, see first20_output.txt")
