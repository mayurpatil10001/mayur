
import asyncio
import os
import sys
import glob

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

async def check_dupes():
    folders = [
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    ]
    
    files_to_scan = []
    for fld in folders:
        if os.path.exists(fld):
            all_f = glob.glob(os.path.join(fld, '*3Q_sim14.data'))
            # Just take a week of data
            files_to_scan.extend([f for f in all_f if os.path.basename(f)[17:27] >= "2026-02-10"])
    
    all_unique_fills = []
    
    print(f"Checking {len(files_to_scan)} files for overlapping fills...")
    
    for f in files_to_scan:
        try:
            fills = _parse_file_nitro(f, target_sym="CL")
            for fill in fills:
                all_unique_fills.append(fill)
        except: pass

    # Sort and check for overlaps
    all_unique_fills.sort(key=lambda x: x['timestamp'])
    
    dupes = 0
    for i in range(len(all_unique_fills)-1):
        f1 = all_unique_fills[i]
        f2 = all_unique_fills[i+1]
        
        # If they match on almost everything but have different offsets/files
        if f1['symbol'] == f2['symbol'] and f1['price'] == f2['price'] and f1['side'] == f2['side'] and f1['quantity'] == f2['quantity']:
             # If timestamps are within 1 second
             # ... simplified string check ...
             if f1['timestamp'][:19] == f2['timestamp'][:19]:
                  dupes += 1
                  if dupes < 5:
                      print(f"DUPE FOUND: {f1['timestamp']} vs {f2['timestamp']}")
                      print(f"  F1: {f1['account_name']}, Qty {f1['quantity']}, Prc {f1['price']}, Side {f1['side']}")
                      print(f"  F1-File: {os.path.basename(f1['offset'] if isinstance(f1.get('offset'), str) else 'unknown')}...") # Just for info

    print(f"Total Dupes found in sample: {dupes}")

if __name__ == "__main__":
    asyncio.run(check_dupes())
