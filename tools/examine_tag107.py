import struct
import os

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.TS_4.data"
with open(fp, "rb") as f:
    data = f.read()

offset = 0
found = 0
while offset < len(data) - 8 and found < 10:
    tag = struct.unpack('<I', data[offset:offset+4])[0]
    length = struct.unpack('<I', data[offset+4:offset+8])[0]
    if tag == 107:
        found += 1
        print(f"\n--- Tag 107 found at {offset} | Length: {length} ---")
        val = data[offset+8 : offset+8+length]
        hex_str = " ".join(f"{b:02x}" for b in val)
        print(f"Hex: {hex_str}")
        # Try to see if there's a double inside
        for i in range(0, len(val)-7, 8):
            try:
                d = struct.unpack('<d', val[i:i+8])[0]
                if 20 < d < 25000:
                    print(f"  Double at {i}: {d}")
            except: pass
        offset += 8 + length
    else:
        offset += 1
