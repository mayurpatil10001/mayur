import os
import sys

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, _ = _parse_file_nitro(target_fp)
v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']

oid_map = {}
for f in v_fills:
    oid = f.get('order_id')
    if oid not in oid_map: oid_map[oid] = []
    oid_map[oid].append(f)

print(f"Checking OrderID Re-use in {target_fp}")
for oid, fills in oid_map.items():
    if len(fills) > 1:
        print(f"\nOID: {oid} found {len(fills)} times:")
        for f in fills:
            print(f"  {f['timestamp']} | {f['side']} | Qty:{f['quantity']} | {f['msgtxt'][:40]}")
