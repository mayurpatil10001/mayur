import os
import struct
import re

def inspect_dec18():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    
    with open(data_path, "rb") as bf:
        d = bf.read()
    
    offset = 0
    fills = []
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            s_lower = s.lower()
            if "trade simulation fill" in s_lower or "fill: " in s_lower:
                fills.append(s)
        offset = val_end
        
    print(f"File: {os.path.basename(data_path)}")
    print(f"Total Fills in binary for this day: {len(fills)}")
    # Print fills around 04:05
    print("\nFills containing '04:05':")
    for f in fills:
        if "04:05" in f:
            print(f"  - {f}")
            
    no_note = [f for f in fills if "AT_NQ_TM" not in f]
    print(f"\nFills without 'AT_NQ_TM' note: {len(no_note)}")
    if no_note:
        print("First 3 examples of no-note fills:")
        for f in no_note[:3]:
            print(f"  - {f}")

if __name__ == "__main__":
    inspect_dec18()
