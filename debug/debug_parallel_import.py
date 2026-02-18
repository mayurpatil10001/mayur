from trading_platform.services.binary_log_parser import BinaryLogParser
import asyncio
import os
import glob
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
    parser = BinaryLogParser(db_path=db_path)
    
    # Target only SIM15 files from Feb 2026
    log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    # Manual filter for Feb 7-17
    all_files = glob.glob(os.path.join(log_dir, "*3Q_sim15*.data"))
    target_files = []
    for f in all_files:
        fn = os.path.basename(f)
        if "2026-02-" in fn:
            day = int(fn.split("2026-02-")[1].split("_")[0])
            if 7 <= day <= 17:
                target_files.append(f)
                
    print(f"Targeting {len(target_files)} files for Parallel Import Test.")
    for f in target_files:
        print(f"  {os.path.basename(f)}")
        
    # Run import (mimicking full run logic using list of paths)
    # The run_import method takes a list of directory paths, NOT file paths.
    # But wait, looking at code: 
    # for path in paths: ... glob.glob(os.path.join(cp, "*.data"))
    # So I can't pass file list directly to run_import.
    
    # However, I can subclass or monkeypatch, OR I can just pass the directory 
    # and rely on the parser to find them, BUT I want to isolate these files.
    
    # Let's modify run_import signature? No, let's use a temporary directory?
    # Or just modify the parser instance's run_import to accept file list overrides?
    # No, let's just use the `days_lookback` to restrict it to last 15 days!
    # Feb 17 - 15 days = Feb 2. This covers the range.
    
    print("Running parser with days_lookback=15...")
    await parser.run_import([log_dir], account_filter=["3Q_SIM15"], days_lookback=15)
    print("Import finished.")
    print(parser.message)
    print(parser.stats)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_test())
