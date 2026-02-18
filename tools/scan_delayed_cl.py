
import os
import glob
import asyncio
import sys

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import _parse_file_nitro

async def scan_delayed_2024():
    path = r'D:\SierraChart_Delayed_Simulated\TradeActivityLogs'
    all_files = glob.glob(os.path.join(path, '*3Q_sim14*'), recursive=False)
    files_2024 = [f for f in all_files if "2024-" in os.path.basename(f)]
    files_2024.sort()
    
    print(f"Scanning {len(files_2024)} files from 2024 in Delayed_Simulated...")
    
    results = {}
    
    for f in files_2024:
        fn = os.path.basename(f)
        try:
            fills = _parse_file_nitro(f, target_sym="CL")
            if fills:
                cl_fills = [fill for fill in fills if fill['symbol'].startswith('CL')]
                if cl_fills:
                    ym = fn[17:24]
                    results[ym] = results.get(ym, 0) + len(cl_fills)
        except:
            pass
            
    print("\nCL Fills found by month in Delayed_Simulated:")
    for ym in sorted(results.keys()):
        print(f"{ym}: {results[ym]} fills")

if __name__ == "__main__":
    asyncio.run(scan_delayed_2024())
