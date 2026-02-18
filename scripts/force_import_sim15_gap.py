from trading_platform.services.binary_log_parser import BinaryLogParser
import asyncio
import os
import glob
import logging

logging.basicConfig(level=logging.INFO)

async def run_missing_import():
    db_path = r'c:\SierraChart\SC results WF\trading_platform.db'
    parser = BinaryLogParser(db_path=db_path)
    
    # We identified missing files between Feb 06 and Feb 17
    # Feb 08, 09, 10, 11, 12, 13, 16
    
    log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    
    print("Forcing import of missing SIM15 logs...")
    
    # We will use the parser's logic but ensure all fills are captured.
    # The issue might be that these files were "processed" but not saved?
    # Or maybe the dates are weird?
    
    # Let's run an import specifically for this time window using days_lookback
    # Today is Feb 17. 
    # Gap is roughly Feb 6 to Feb 17.
    # That is last 12 days.
    
    await parser.run_import([log_dir], account_filter=["3Q_SIM15"], days_lookback=20)
    
    print("Import Done.")
    print(parser.stats)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_missing_import())
