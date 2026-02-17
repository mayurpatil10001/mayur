import struct
import re
import datetime
import os

def check_file(fp):
    print(f"Checking {fp}")
    if not os.path.exists(fp):
        print("File not found")
        return
    with open(fp, "rb") as f:
        data = f.read()
    
    # Simple search for "Trading Evaluator" fills
    pattern = rb"Bid: ([\d\.]+)\s+Ask: ([\d\.]+)\s+Last: ([\d\.]+)"
    
    count = 0
    symbols = set()
    for m in re.finditer(pattern, data):
        count += 1
        # Search backwards for symbol
        nearby = data[max(0, m.start()-200):m.start()]
        strings = re.findall(b'[A-Z]{2,}', nearby)
        if strings: 
            sym = strings[-1].decode()
            symbols.add(sym)
            if count <= 10:
                print(f"Fill {count}: Symbol={sym}")
    
    print(f"Total potential fills: {count}")
    print(f"Unique symbols found: {symbols}")

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-07-08_UTC.TS_4.data"
check_file(fp)
