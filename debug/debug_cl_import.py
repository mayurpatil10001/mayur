from trading_platform.services.binary_log_parser import BinaryLogParser
import asyncio
import os

async def debug_cl_file():
    parser = BinaryLogParser()
    # Possible paths based on user screenshots
    base_dirs = [
        r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
        r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    ]
    
    file_to_debug = None
    for d in base_dirs:
        path = os.path.join(d, "TradeActivityLog_2024-06-14_UTC.CL-IPS_TM_13.data")
        if os.path.exists(path):
            file_to_debug = path
            break
            
    if not file_to_debug:
        print("Target file not found in known directories")
        # Try to find ANY CL file
        for d in base_dirs:
            if os.path.exists(d):
                files = [f for f in os.listdir(d) if "CL" in f.upper() and f.endswith(".data")]
                if files:
                    file_to_debug = os.path.join(d, files[0])
                    break
                    
    if not file_to_debug:
        print("No CL .data files found at all")
        return

    print(f"DEBUGGING FILE: {file_to_debug}")
    
    # Check if the file is reachable
    print(f"File Size: {os.path.getsize(file_to_debug)} bytes")
    
    fills = parser._parse_file(file_to_debug)
    print(f"Raw Fills found: {len(fills)}")
    
    if fills:
        print("First 5 fills samples:")
        for f in fills[:5]:
            print(f)
        
        trades = parser._pairs_to_trades(fills)
        print(f"Synthesized Trades: {len(trades)}")
        if trades:
            print("First 2 trades samples:")
            for t in trades[:2]:
                print(t)
    else:
        # If no fills, dump some bytes to see if "Last:" exists
        with open(file_to_debug, "rb") as f:
            data = f.read(10000)
            if b"Last:" in data or b"LastPrice" in data:
                print("'Last:' signature found in first 10KB")
            else:
                print("'Last:' signature NOT found in first 10KB")

if __name__ == "__main__":
    asyncio.run(debug_cl_file())
