import struct
import os

def search_price(fp, target_price):
    with open(fp, "rb") as f:
        data = f.read()
    
    # Search for price as string "68.87"
    price_str = f"{target_price:.2f}".encode()
    matches_str = list(re.finditer(re.escape(price_str), data))
    print(f"Found {len(matches_str)} matches for string '{price_str.decode()}'")
    
    for m in matches_str[:5]:
        print(f"Match at {m.start()}: {data[m.start()-50:m.start()+100].decode('ascii', errors='ignore')}")

import re
fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-11-18_UTC.3Q_sim7.data"
search_price(fp, 68.87)
