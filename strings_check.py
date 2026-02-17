
import os
import struct

def strings(filename, min_len=4):
    with open(filename, "rb") as f:
        content = f.read()
    
    # Text Search
    print(f"--- STRINGS found in {os.path.basename(filename)} ---")
    result = ""
    for byte in content:
        if 32 <= byte <= 126:
            result += chr(byte)
        else:
            if len(result) >= min_len:
                # Filter for interesting stuff
                if "CL" in result or "ES" in result or "3Q" in result or "IPS" in result:
                    print(f"  Found string: {result}")
            result = ""
    
    # Float Search
    print(f"--- FLOATS found in {os.path.basename(filename)} ---")
    targets = [60.53, 59.28, 59.25, 59.48, 6847.5, 6850.0]
    
    # We scan overlapping 8-byte chunks
    for i in range(len(content) - 8):
        chunk = content[i:i+8]
        try:
            val = struct.unpack('<d', chunk)[0]
            for t in targets:
                if abs(val - t) < 0.0001:
                    print(f"  Found float {t} at offset {i}: {val}")
        except:
            pass

def check_files():
    base_dir = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs"
    
    f1 = os.path.join(base_dir, "TradeActivityLog_2026-01-19_UTC.3Q_sim14.data")
    strings(f1)
    
    # f2 = os.path.join(base_dir, "TradeActivityLog_2025-12-03_UTC.ES-IPS_TM_5dupl.data")
    # strings(f2)

if __name__ == "__main__":
    check_files()
