import asyncio
import os
from trading_platform.services.binary_log_parser import importer

async def main():
    paths = [r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"]
    account_filter = ["TS_4"]
    filter_symbol = "CL"
    
    print(f"Starting import for {filter_symbol} on {account_filter}...")
    await importer.run_import(paths, filter_symbol=filter_symbol, account_filter=account_filter)
    print(f"Import finished: {importer.message}")
    print(f"Stats: {importer.stats}")

if __name__ == "__main__":
    asyncio.run(main())
