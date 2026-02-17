import re
import os
import struct

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

offset = 0
found = 0
while offset < len(data) - 12:
    tag = struct.unpack('<I', data[offset:offset+4])[0]
    length = struct.unpack('<I', data[offset+4:offset+8])[0]
    if tag == 104:
        s = data[offset+8 : offset+8+length].decode('ascii', errors='ignore')
        if any(x in s.lower() for x in ["bought", "sold", "fill", "trade"]):
            found += 1
            if found <= 50:
                print(f"[{found}] {s}")
        offset += 8 + length
    else:
        offset += 1

print(f"Total found: {found}")
