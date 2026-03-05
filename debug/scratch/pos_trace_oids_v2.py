import os
import sys

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, _ = _parse_file_nitro(target_fp)
v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']
v_fills.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# Dedupe
deduped = []
seen = set()
for f in v_fills:
    oid = f.get('order_id')
    sig = (round(f.get('ts_val', 0) * 2) / 2.0, f['price'], f['side'], f['quantity'], oid)
    if sig not in seen:
        deduped.append(f)
        seen.add(sig)

print(f"Full Position Trace for V_SIM16 (ID Trace)")
print("-" * 120)

net_pos = 0
limit = 3

for f in deduped:
    side = f['side']
    qty = f['quantity']
    ts = f['timestamp']
    oid = str(f.get('order_id', 'N/A'))
    msg = str(f.get('msgtxt', ''))[:50]
    
    pre_pos = net_pos
    status = "OK"
    
    if side == 'BUY':
        intended = net_pos + qty
        if intended > limit:
            allowed = max(0, limit - net_pos)
            qty = allowed
        net_pos += qty
    else:
        intended = net_pos - qty
        if intended < -limit:
            allowed = max(0, limit + net_pos)
            qty = allowed
        net_pos -= qty
        
    print(f"{ts:25} | {side:5} | Qty:{f['quantity']:1} | Pos:{net_pos:2} | OID:{oid:10} | {msg}")
