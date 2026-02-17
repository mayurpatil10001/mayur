
import struct
import os

def scan_3q_v3():
    f = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-19_UTC.3Q_sim14.data"
    target_price = 59.28
    
    with open(f, 'rb') as f:
        content = f.read()
    
    print(f"File size: {len(content)}")
    
    # Scan for 59.28 as a double
    found_count = 0
    for i in range(len(content)-8):
        val = struct.unpack('<d', content[i:i+8])[0]
        if abs(val - target_price) < 0.0001:
            found_count += 1
            print(f"\nFound 59.28 at offset {i}")
            # Show +/- 200 bytes around it
            s = max(0, i - 200)
            e = min(len(content), i + 200)
            chunk = content[s:e]
            # Print printable strings in chunk
            import re
            strings = re.findall(b"[A-Za-z0-9_]{3,}", chunk)
            print(f"  Strings nearby: {strings}")
            
    if found_count == 0:
        print("Price 59.28 NOT FOUND in binary file at all.")

if __name__ == "__main__":
    scan_3q_v3()
