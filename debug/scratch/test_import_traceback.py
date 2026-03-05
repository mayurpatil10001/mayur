import sys
import asyncio
sys.path.append(r'c:\SierraChart\SC results WF')
from trading_platform.services.binary_log_parser import importer

async def main():
    try:
        await importer.run_import(paths=['D:\\SierraChart_Simulated_Feed\\TradeActivityLogs'], filter_symbol='NQ', account_filter=None, days_lookback=200)
        print("Success:", importer.stats)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
