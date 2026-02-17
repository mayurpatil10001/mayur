from trading_platform.services.binary_log_parser import BinaryLogParser
import asyncio
import os

async def test():
    parser = BinaryLogParser()
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    files = os.listdir(path)
    binary_files = [f for f in files if f.endswith('.data')]
    if not binary_files:
        print("No .data files found")
        return
        
    file_path = os.path.join(path, binary_files[0])
    print(f"Testing on {file_path}")
    
    fills = parser._parse_file(file_path)
    print(f"Found {len(fills)} matches in _parse_file")
    if fills:
        buys = len([f for f in fills if f['side'] == 'BUY'])
        sells = len([f for f in fills if f['side'] == 'SELL'])
        print(f"Sides: BUY={buys}, SELL={sells}")
        
        trades = parser._pairs_to_trades(fills)
        print(f"Synthesized {len(trades)} trades")
        if trades:
            print(f"Sample trade: {trades[0]}")
        else:
            # Check why no trades
            # Print first 10 sides/timestamps
            print("First 10 fills:")
            for f in fills[:10]:
                print(f"{f['timestamp']} - {f['side']} - {f['price']}")

if __name__ == "__main__":
    asyncio.run(test())
