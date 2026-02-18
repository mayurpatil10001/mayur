
import asyncio
import os
import sys

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser

async def reimport_sim13():
    parser = BinaryLogParser()
    folders = [
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\SierraChartInstance_5\TradeActivityLogs',
        r'D:\SierraChart_Simulated_Feed\TradeActivityLogs'
    ]
    
    print("Starting Global Re-Import for 3Q_SIM13...")
    await parser.run_import(
        paths=folders,
        filter_symbol="CL",
        account_filter=["3Q_SIM13"],
        days_lookback=None
    )
    print("Import Finished.")

if __name__ == "__main__":
    asyncio.run(reimport_sim13())
