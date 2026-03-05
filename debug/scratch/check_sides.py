import os
import glob
import struct
import re

def check_fill_sides():
    data_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    pattern = os.path.join(data_dir, "*v_sim16*.data")
    files = glob.glob(pattern)
    files = sorted(list(set(files)))

    buys = 0
    sells = 0
    unknown = 0
    
    # Just check first file
    if not files: return
    
    fp = files[0]
    with open(fp, "rb") as bf:
        d = bf.read()
    
    offset = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore').strip()
            s_lower = s.lower()
            if "trade simulation fill" in s_lower or "fill: " in s_lower:
                if any(x in s_lower for x in ["buy", "bought", "long"]):
                    buys += 1
                elif any(x in s_lower for x in ["sell", "sold", "short"]):
                    sells += 1
                else:
                    unknown += 1
        offset = val_end
        
    print(f"File: {os.path.basename(fp)}")
    print(f"Buys: {buys}, Sells: {sells}, Unknown: {unknown}")

if __name__ == "__main__":
    check_fill_sides()
