import asyncio
import sys
import os

# Add parent dir to path
sys.path.append(os.getcwd())

from trading_platform.services.binary_log_parser import BinaryLogParser

async def test_ts4():
    parser = BinaryLogParser()
    path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    if not os.path.exists(path):
        print(f"Path does not exist: {path}")
        return

    print(f"Starting test import for TS_4 on CL from {path}...")
    await parser.run_import([path], filter_symbol="CL", account_filter=["TS_4"])
    
    print(f"Final Message: {parser.message}")
    print(f"Stats: {parser.stats}")

if __name__ == "__main__":
    asyncio.run(test_ts4())
