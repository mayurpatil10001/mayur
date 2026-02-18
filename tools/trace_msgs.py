
import struct
import os
import re

def trace_fill_msgs():
    bin_file = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    with open(bin_file, 'rb') as f:
        d = f.read()
    
    count = 0
    offset = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset:offset+8])
        if tag == 0x68:
            s = d[offset+8:offset+8+length].decode(errors='ignore')
            s_lower = s.lower()
            if any(x in s_lower for x in ["trade simulation fill", "processed execution report", "fill: ", "internal position"]):
                oid_m = re.search(r"internalorderid[:\s]*(\d+)", s_lower)
                oid = oid_m.group(1) if oid_m else "N/A"
                print(f"[{oid}] MSG: {s.strip()[:150]}")
                count += 1
        offset += 8 + length

if __name__ == "__main__":
    trace_fill_msgs()
