import re
import os
import struct

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

# Search for any message Tag (0x68 = 104)
# Tag is 4 bytes, Length is 4 bytes.
offset = 0
found_fills = 0
while offset < len(data) - 8:
    tag = struct.unpack('<I', data[offset:offset+4])[0]
    length = struct.unpack('<I', data[offset+4:offset+8])[0]
    if tag == 104:
        val = data[offset+8 : offset+8+length].decode('ascii', errors='ignore')
        if "fill" in val.lower() or "bought" in val.lower() or "sold" in val.lower():
            found_fills += 1
            if found_fills <= 20:
                print(f"Fill {found_fills}: {val}")
        offset += 8 + length
    else:
        offset += 1 # Brute force search for next 104 if we are lost

print(f"Total fills found via Tag 104: {found_fills}")
