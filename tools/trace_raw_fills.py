
import struct
import re
import os

def trace_raw_fills():
    # Use one of the newer files since we know they have CL trades
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-16_UTC.3Q_sim14.data'
    
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024) # Read first 10MB
        
    offset = 0
    file_len = len(d)
    count = 0
    
    while offset < file_len - 8 and count < 10:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore')
            if "trade simulation fill" in s.lower() and "CL" in s:
                print(f"RAW MSG: {s}")
                count += 1
        
        offset = val_end

if __name__ == "__main__":
    trace_raw_fills()
