import re
import os
import struct

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

# Brute force search for "Fill" or "Trading Evaluator"
# And see what the nearest Symbol (Tag 103) is
offset = 0
found = 0
current_sym = "Unknown"
while offset < len(data) - 8:
    try:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        if tag == 103: # Symbol
            current_sym = data[offset+8 : offset+8+length].decode('ascii', errors='ignore').strip('\x00').strip()
            offset += 8 + length
        elif tag == 104: # Message
            msg = data[offset+8 : offset+8+length].decode('ascii', errors='ignore')
            if "filled" in msg.lower() or "price" in msg.lower():
                found += 1
                if found <= 50:
                    print(f"Fill {found} | Symbol: {current_sym} | Msg: {msg[:100]}...")
            offset += 8 + length
        else:
            offset += 1
    except:
        offset += 1

print(f"Total found: {found}")
