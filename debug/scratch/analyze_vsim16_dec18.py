import os
import struct
import re
from datetime import datetime

def analyze_vsim16_dec18_details():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    
    with open(data_path, "rb") as bf:
        d = bf.read()
    
    offset = 0
    fills = []
    current_ts = "Unknown"
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        if val_end > len(d): break
        
        if tag == 0x66: # Time
            # Logic to parse timestamp (SCDateTime double or Unix micro)
            from datetime import timezone
            value_bytes = d[val_start:val_end]
            if len(value_bytes) >= 8:
                try:
                    val = struct.unpack('<d', value_bytes[:8])[0]
                    if 30000 < val < 70000:
                        base = datetime(1899, 12, 30)
                        dt = base + (datetime.now() - datetime.now()) # placeholder
                        import datetime as dt_mod
                        dt = dt_mod.datetime(1899, 12, 30) + dt_mod.timedelta(days=val)
                        current_ts = dt.strftime("%Y-%m-%d %H:%M:%S.%f")
                except: pass

        elif tag == 0x68: # Message
            s = d[val_start:val_end].decode(errors='ignore').strip()
            s_lower = s.lower()
            if ("trade simulation fill" in s_lower or "fill: " in s_lower) and "updated internal position" not in s_lower:
                fills.append({"ts": current_ts, "msg": s})
        
        offset = val_end
        
    print(f"Detailed analysis of V_SIM16 - 2025-12-18")
    print("-" * 50)
    
    no_note = [f for f in fills if "AT_NQ_TM" not in f['msg']]
    print(f"Total fills: {len(fills)}")
    print(f"Fills without Note: {len(no_note)}")
    print("\nListing Fills MISSING Notes:")
    for f in no_note:
        print(f"  Time: {f['ts']} | Message: {f['msg']}")

if __name__ == "__main__":
    analyze_vsim16_dec18_details()
