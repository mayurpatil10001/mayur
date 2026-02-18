import struct
import os
from collections import Counter

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

tags = Counter()
offset = 0
while offset < len(data) - 8:
    try:
        tag = struct.unpack('<I', data[offset:offset+4])[0]
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        if 0 < length < 10000 and tag < 1000:
            tags[tag] += 1
            offset += 8 + length
        else:
            offset += 1
    except:
        offset += 1

print(f"Tag distribution: {tags}")
