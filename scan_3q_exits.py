
import struct
import os

def scan_3q_exits():
    f = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-19_UTC.3Q_sim14.data"
    targets = [59.48, 59.00, 59.28]
    
    with open(f, 'rb') as f:
        content = f.read()
    
    # Scan for targets as double
    for t in targets:
        count = 0
        for i in range(len(content)-8):
            val = struct.unpack('<d', content[i:i+8])[0]
            if abs(val - t) < 0.0001:
                print(f"Found {t} at offset {i}")
                count += 1
        if count == 0:
            print(f"Price {t} NOT FOUND")

if __name__ == "__main__":
    scan_3q_exits()
