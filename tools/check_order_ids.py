
import asyncio
import os
import sys
import glob

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import _parse_file_nitro

async def check_order_ids():
    folders = [
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    ]
    
    files_to_scan = []
    for fld in folders:
        if os.path.exists(fld):
            all_f = glob.glob(os.path.join(fld, 'TradeActivityLog_2026-02-16*.data'))
            files_to_scan.extend(all_f)
    
    all_fills = []
    for f in files_to_scan:
        try:
            fills = _parse_file_nitro(f, target_sym="CL")
            all_fills.extend(fills)
        except: pass

    all_fills.sort(key=lambda x: x['timestamp'])
    
    for i in range(len(all_fills)-1):
        f1 = all_fills[i]
        f2 = all_fills[i+1]
        
        if f1['price'] == f2['price'] and f1['side'] == f2['side'] and f1['timestamp'][:19] == f2['timestamp'][:19]:
            print(f"MATCH: {f1['timestamp']} OID={f1['order_id']} | {f2['timestamp']} OID={f2['order_id']}")

if __name__ == "__main__":
    asyncio.run(check_order_ids())
