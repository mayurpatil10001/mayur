
import os
import glob
import asyncio
import sys

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import _parse_file_nitro

async def scan_cross_symbols():
    folders = {
        "CL": r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        "ES": r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs',
        "NQ": r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    }
    
    print("Checking SIM14 trades across ALL symbol folders for 2024...")
    
    global_results = {}
    
    for sym, path in folders.items():
        all_files = glob.glob(os.path.join(path, '*3Q_sim14*'), recursive=False)
        files_2024 = [f for f in all_files if "2024-" in os.path.basename(f)]
        files_2024.sort()
        
        print(f"  Scanning {sym} folder ({len(files_2024)} files)...")
        
        for f in files_2024:
            try:
                # Parse without target_sym to see ALL symbols
                fills = _parse_file_nitro(f, target_sym=None)
                if fills:
                    for fill in fills:
                        fsym = fill['symbol']
                        base = fsym[:2] if len(fsym) > 2 else fsym
                        global_results[base] = global_results.get(base, 0) + 1
            except: pass
            
    print("\nTotal Fill counts by base symbol for SIM14 in 2024 logs:")
    for base, count in sorted(global_results.items(), key=lambda x: x[1], reverse=True):
        print(f"  {base}: {count} fills")

if __name__ == "__main__":
    asyncio.run(scan_cross_symbols())
