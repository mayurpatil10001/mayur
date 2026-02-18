
import os
import glob
import asyncio
import sys

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import _parse_file_nitro

async def scan_all_cl_2024():
    path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs'
    all_files = glob.glob(os.path.join(path, 'TradeActivityLog_2024-*.data'), recursive=False)
    all_files.sort()
    
    # Filter for first half of 2024
    files_scan = [f for f in all_files if "-01-" in f or "-02-" in f or "-05-" in f or "-06-" in f or "-07-" in f]
    
    print(f"Scanning {len(files_scan)} files for ANY CL trades in early 2024...")
    
    acc_map = {}
    
    for f in files_scan:
        try:
            fills = _parse_file_nitro(f, target_sym="CL")
            if fills:
                for fill in fills:
                    if fill['symbol'].startswith('CL'):
                        acc = fill['account_name']
                        acc_map[acc] = acc_map.get(acc, 0) + 1
        except:
            pass
            
    print("\nCL Fills found by Account Name in early 2024 (Instance 4):")
    for acc, count in sorted(acc_map.items()):
        print(f"{acc}: {count} fills")

if __name__ == "__main__":
    asyncio.run(scan_all_cl_2024())
