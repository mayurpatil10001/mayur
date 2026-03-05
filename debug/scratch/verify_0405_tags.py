import os
import struct
import re
import datetime

def get_sc_time_v3(value_bytes):
    if len(value_bytes) >= 8:
        try:
            q_val = struct.unpack('<q', value_bytes[:8])[0]
            if 3000000000000000 < q_val < 4500000000000000:
                return datetime.datetime(1899, 12, 30) + datetime.timedelta(microseconds=q_val)
        except: pass
    return None

def verify_0405_tags():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    with open(data_path, "rb") as bf: d = bf.read()
    
    offset = 0
    current_dt = None
    target_found = False
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        
        if tag == 0x66:
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt: current_dt = dt
        
        # Check for 04:05 NY (09:05 UTC)
        if current_dt and current_dt.hour == 9 and current_dt.minute == 5:
            if tag == 0x68:
                s = d[val_start:val_end].decode(errors='ignore').strip()
                if "simulation fill" in s.lower() and "25046.75" in s:
                    print(f"\n--- 04:05 MATCH AT {current_dt} ---")
                    print(f"Message (0x68): {s}")
                    
                    # Look for tag 0x82 nearby
                    # I'll dump 1KB around this area
                    dump_start = max(0, offset - 500)
                    dump_end = min(len(d), offset + 500)
                    sub = dump_start
                    found_82 = False
                    while sub < dump_end:
                        t, l = struct.unpack('<II', d[sub:sub+8])
                        v = d[sub+8:sub+8+l]
                        if t == 0x82:
                            print(f"  !!!!! FOUND TAG 0x82 at {sub:06x} | Len {l} | Val: {v.decode(errors='ignore')}")
                            found_82 = True
                        sub += 8 + l
                    if not found_82:
                        print("  No Tag 0x82 found in this record block.")
                    return

        offset = val_end

if __name__ == "__main__":
    verify_0405_tags()
