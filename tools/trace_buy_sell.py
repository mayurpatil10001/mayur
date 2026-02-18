
import struct
import re
import os

def trace_buy_sell():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-08-12_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024)
        
    offset = 0
    file_len = len(d)
    count = 0
    
    while offset < file_len - 8 and count < 30:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore')
            if ("Buy" in s or "Sell" in s) and "CL" in s:
                print(f"MSG: {s.strip()}")
                count += 1
        
        offset = val_end

if __name__ == "__main__":
    trace_buy_sell()
