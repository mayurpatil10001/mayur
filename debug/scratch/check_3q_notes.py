import os
import struct
import re

def check_3q_sim14_notes():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-18_UTC.3Q_sim14.data"
    if not os.path.exists(data_path): return

    with open(data_path, "rb") as bf:
        d = bf.read()
    
    offset = 0
    fills = []
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            if "trade simulation fill" in s.lower():
                fills.append(s)
        offset = val_end
        
    print(f"Sample notes for 3Q_sim14 (CL):")
    for f in fills[:5]:
        print(f"  - {f}")
        
    unique_patterns = set()
    for f in fills:
        # Extract potential note (anything before "Trading Evaluator" or "Info:")
        parts = f.split('Trading Evaluator')
        if len(parts) > 0:
            unique_patterns.add(parts[0].strip())
    
    print("\nUnique Note Patterns found for 3Q_sim14:")
    for p in unique_patterns:
        print(f"  - '{p}'")

if __name__ == "__main__":
    check_3q_sim14_notes()
