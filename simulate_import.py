from trading_platform.services.binary_log_parser import BinaryLogParser
import asyncio
import os

async def simulate_frontend_import():
    parser = BinaryLogParser()
    path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    # These are some of the accounts seen in screenshots
    selected_accounts = ["3Q_sim13", "3Q_sim15", "3Q_sim7", "CL-IPSMUD1", "CL-IPS_TM_10"]
    symbol = "CL"
    
    print(f"Starting simulated import for {symbol} on {len(selected_accounts)} accounts...")
    
    # We need to set running=True manually because we are calling run_import directly
    # or just let it run.
    await parser.run_import([path], symbol, selected_accounts)
    
    print(f"FINAL STATUS: {parser.message}")
    print(f"STATS: {parser.stats}")

if __name__ == "__main__":
    if os.path.exists(r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"):
        asyncio.run(simulate_frontend_import())
    else:
        print("Path not found, check D: drive")
