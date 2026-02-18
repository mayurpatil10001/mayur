import struct
import os
import re

def dump_cl_messages(fp):
    with open(fp, "rb") as f:
        data = f.read()
    
    offset = 0
    found = 0
    while offset < len(data) - 12:
        try:
            tag = struct.unpack('<I', data[offset:offset+4])[0]
            length = struct.unpack('<I', data[offset+4:offset+8])[0]
            if tag == 104:
                val = data[offset+8 : offset+8+length].decode('ascii', errors='ignore')
                if "CL" in val and ("fill" in val.lower() or "price" in val.lower()):
                    found += 1
                    print(f"\n--- CL Message {found} [{offset}] ---")
                    print(val)
                    if found >= 20: break
                offset += 8 + length
            else:
                offset += 1
        except:
            offset += 1

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-06_UTC.TS_4.data"
dump_cl_messages(fp)
