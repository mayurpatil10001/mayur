
import asyncio
import os
import sys
from datetime import datetime

# Add project root
sys.path.append(os.getcwd())
from trading_platform.services.binary_log_parser import BinaryLogParser, _parse_file_nitro

async def test_parse_qty():
    parser = BinaryLogParser()
    # Use the file we know has Qty 3
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-16_UTC.3Q_sim14.data'
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Testing parse and QTY extraction for: {file_path}")
    fills = _parse_file_nitro(file_path)
    print(f"Raw fills found: {len(fills)}")
    
    if fills:
        print("First 10 fills (Quantity Check):")
        for f in fills[:10]:
            print(f"  Time: {f['timestamp']}, Qty: {f['quantity']}, Price: {f['price']}, Symbol: {f['symbol']}")
            
        # Try pairing
        trades, unpaired = parser._pairs_to_trades(fills)
        print(f"Trades successfully paired: {len(trades)}")
        if trades:
             print(f"First trade Qty: {trades[0]['quantity']}, PnL: {trades[0]['profit_loss']}")

if __name__ == "__main__":
    asyncio.run(test_parse_qty())
