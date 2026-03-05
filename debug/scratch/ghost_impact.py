import os
import sys
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

# Parse WITH ghost removal (current code)
fills_clean, ghost_map_clean = _parse_file_nitro(target_fp)

# Now let's also get ALL fills including ghosts to compare
# We'll do this by checking the ghost_details.log or by temporarily disabling ghost check

# First: trace the CLEAN fills (ghosts removed)
v_clean = [f for f in fills_clean if f['account_name'] == 'V_SIM16']
v_clean.sort(key=lambda x: (x.get('ts_val', 0), x.get('offset', 0)))

# Dedupe
deduped = []
seen = set()
for f in v_clean:
    sig = (round(f.get('ts_val', 0) * 2) / 2.0, f['price'], f['side'], f['quantity'])
    if sig not in seen:
        deduped.append(f)
        seen.add(sig)

print(f"CLEAN FILLS (ghosts removed): {len(deduped)}")
print(f"Ghosts removed: {ghost_map_clean}")
print()

# Trace position
print(f"{'#':3} | {'Time (NY approx)':20} | {'Side':5} | {'Qty':3} | {'PrePos':6} | {'PostPos':7} | {'OID':12} | {'Note':30} | Status")
print("-" * 150)

net_pos = 0
limit = 3
drift_count = 0

for i, f in enumerate(deduped):
    side = f['side']
    qty = f['quantity']
    ts = f['timestamp']
    oid = str(f.get('order_id', 'N/A'))
    note = str(f.get('note', ''))[:30]
    
    pre_pos = net_pos
    
    if side == 'BUY':
        net_pos += qty
    else:
        net_pos -= qty
    
    status = "OK"
    if abs(net_pos) > limit:
        status = f">>> OVER LIMIT (net={net_pos})"
        drift_count += 1
    
    print(f"{i+1:3} | {ts:25} | {side:5} | {qty:3} | {pre_pos:6} | {net_pos:7} | {oid:12} | {note:30} | {status}")

print(f"\nTotal drift violations: {drift_count}")
print(f"Max |position| observed: {max(abs(sum(f['quantity'] if f['side']=='BUY' else -f['quantity'] for f in deduped[:j+1])) for j in range(len(deduped)))}")
