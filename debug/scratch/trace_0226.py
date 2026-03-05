import asyncio
from trading_platform.services.binary_log_parser import BinaryLogParser

async def test():
    parser = BinaryLogParser(db_path='trading_platform.db')
    await parser.run_import([r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"], account_filter=["V_SIM16"], days_lookback=None)

if __name__ == "__main__":
    asyncio.run(test())
