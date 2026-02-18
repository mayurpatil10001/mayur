
import struct
import re
import os

def trace_all_simulation_fills():
    # Try a very recent file
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    if not os.path.exists(file_path):
        # Try the NQ folder if Instance 4 fails
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'

    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as bf:
        d = bf.read(5 * 1024 * 1024)
        
    offset = 0
    file_len = len(d)
    count = 0
    
    while offset < file_len - 8 and count < 20:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                print(f"RAW MSG: {s.strip()}")
                count += 1
        
        offset = val_end

if __name__ == "__main__":
    trace_all_simulation_fills()
