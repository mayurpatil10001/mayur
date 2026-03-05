
import asyncio
import os
import sys
from datetime import datetime

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser

async def test_parse_old_file():
    parser = BinaryLogParser()
    file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2024-01-22_UTC.3Q_sim14.data'
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    if fills:
        print("First 5 fills (Quantity Check):")
        for f in fills[:5]:
            print(f"  Time: {f['timestamp']}, Qty: {f['quantity']}, Price: {f['price']}, Symbol: {f['symbol']}")
            
        # Try pairing
        trades, unpaired = parser._pairs_to_trades(fills)
        print(f"Trades successfully paired: {len(trades)}")
        if trades:
             print(f"First trade Qty: {trades[0]['quantity']}, PnL: {trades[0]['profit_loss']}")
        
        if trades:
            print("First trade entry time:", trades[0]['entry_time'])

if __name__ == "__main__":
    asyncio.run(test_parse_old_file())
