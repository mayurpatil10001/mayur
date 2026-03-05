import os
import sys
import datetime
from zoneinfo import ZoneInfo

project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_file_nitro, NY_TZ

# Parse BOTH Dec 17 and Dec 18 files
fp17 = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-17_UTC.V_sim16.data"
fp18 = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

fills17, _ = _parse_file_nitro(fp17)
fills18, _ = _parse_file_nitro(fp18)

v17 = [f for f in fills17 if f['account_name'] == 'V_SIM16']
v18 = [f for f in fills18 if f['account_name'] == 'V_SIM16']

v17.sort(key=lambda x: x.get('ts_val', 0))
v18.sort(key=lambda x: x.get('ts_val', 0))

# Check last few fills of Dec 17
print("=== LAST 10 FILLS OF DEC 17 FILE ===")
for f in v17[-10:]:
    try:
        dt = datetime.datetime.fromisoformat(f['timestamp']).replace(tzinfo=ZoneInfo("UTC"))
        ny = dt.astimezone(NY_TZ).strftime("%H:%M:%S")
    except: ny = "?"
    print(f"  {f['timestamp'][:23]} | NY:{ny} | {f['side']:5} Qty:{f['quantity']} | OID:{str(f.get('order_id',''))[:10]}")

print(f"\n=== FIRST 10 FILLS OF DEC 18 FILE ===")
for f in v18[:10]:
    try:
        dt = datetime.datetime.fromisoformat(f['timestamp']).replace(tzinfo=ZoneInfo("UTC"))
        ny = dt.astimezone(NY_TZ).strftime("%H:%M:%S")
    except: ny = "?"
    print(f"  {f['timestamp'][:23]} | NY:{ny} | {f['side']:5} Qty:{f['quantity']} | OID:{str(f.get('order_id',''))[:10]}")

# Check for OVERLAP: fills in Dec17 file that are in the Dec18 UTC window
overlap17 = [f for f in v17 if '2025-12-18' in f['timestamp']]
print(f"\nFills in Dec17 file with Dec18 timestamps: {len(overlap17)}")

# Check for OVERLAP: fills in Dec18 file that have Dec17 timestamps
overlap18 = [f for f in v18 if '2025-12-17' in f['timestamp']]
print(f"Fills in Dec18 file with Dec17 timestamps: {len(overlap18)}")

# Check for DUPLICATE OIDs across files
oids17 = set(str(f.get('order_id', '')) for f in v17 if f.get('order_id'))
oids18 = set(str(f.get('order_id', '')) for f in v18 if f.get('order_id'))
common_oids = oids17 & oids18
print(f"Common OIDs between files: {len(common_oids)}")
if common_oids:
    for oid in list(common_oids)[:5]:
        print(f"  Shared OID: {oid}")

# Carryover position from Dec17
net17 = 0
for f in v17:
    if f['side'] == 'BUY': net17 += f['quantity']
    else: net17 -= f['quantity']
print(f"\nDec17 ending raw net position: {net17}")

# FIFO position from Dec 17
buys, sells = [], []
for f in v17:
    qty = f['quantity']
    if f['side'] == 'BUY':
        while qty > 0 and sells:
            s = sells[0]
            m = min(qty, s['qty'])
            qty -= m; s['qty'] -= m
            if s['qty'] <= 0: sells.pop(0)
        if qty > 0: buys.append({'qty': qty})
    else:
        while qty > 0 and buys:
            b = buys[0]
            m = min(qty, b['qty'])
            qty -= m; b['qty'] -= m
            if b['qty'] <= 0: buys.pop(0)
        if qty > 0: sells.append({'qty': qty})

open_l = sum(b['qty'] for b in buys)
open_s = sum(s['qty'] for s in sells)
print(f"Dec17 ending FIFO: Open Long={open_l}, Open Short={open_s}")
