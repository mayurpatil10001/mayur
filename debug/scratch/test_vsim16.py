import asyncio
from trading_platform.services.binary_log_parser import BinaryLogParser

async def test():
    parser = BinaryLogParser(db_path='trading_platform.db')
    print("Testing parser...")
    await parser.run_import([r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"], account_filter=["V_SIM16"])
    
    print("Import Stats:", parser.stats)
    bdown = parser.stats.get('breakdown', {}).get('V_SIM16', {})
    print("V_SIM16 Breakdown:", bdown)
    
if __name__ == "__main__":
    asyncio.run(test())
