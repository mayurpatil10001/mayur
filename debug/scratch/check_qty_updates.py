import os
import sys

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills, _ = _parse_file_nitro(target_fp)
v_fills = [f for f in fills if f['account_name'] == 'V_SIM16']

oid_qtys = {}
for f in v_fills:
    oid = f.get('order_id')
    if not oid: continue
    if oid not in oid_qtys: oid_qtys[oid] = []
    oid_qtys[oid].append(f['quantity'])

print(f"Checking for OID Qty updates in {target_fp}")
for oid, qtys in oid_qtys.items():
    if len(set(qtys)) > 1:
        print(f"  OID: {oid} has different Qtys: {qtys}")
