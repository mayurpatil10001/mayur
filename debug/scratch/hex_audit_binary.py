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

def hex_audit():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    with open(data_path, "rb") as bf: d = bf.read()
    
    offset = 0
    current_dt = None
    
    # We want to find the record for 03:05 NY (08:05 UTC)
    target_utc_hour = 8
    target_utc_min = 5
    
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start, val_end = offset + 8, offset + 8 + length
        if val_end > len(d): break
        
        if tag == 0x66:
            dt = get_sc_time_v3(d[val_start:val_end])
            if dt: current_dt = dt
        
        # If we are in the target window, dump all tags in this "record"
        # Since SC files are stream of tags, a record is roughly tags between timestamps
        if current_dt and current_dt.hour == target_utc_hour and current_dt.minute == target_utc_min:
            # Check if this tag is a message string containing "simulation fill"
            if tag == 0x68:
                s = d[val_start:val_end].decode(errors='ignore').strip()
                if "simulation fill" in s.lower():
                    print(f"\n--- MATCH AT {current_dt} ---")
                    print(f"Message Tag (0x68): {s}")
                    
                    # Search back and forward for other tags at this same timestamp
                    # Actually, let's just dump nearby tags
                    dump_start = max(0, offset - 500)
                    dump_end = min(len(d), offset + 500)
                    print(f"Hex Dump around offset {offset}:")
                    # (Simplified) Just listing tags around it
                    sub_off = dump_start
                    while sub_off < dump_end:
                        t, l = struct.unpack('<II', d[sub_off : sub_off+8])
                        v = d[sub_off+8 : sub_off+8+l]
                        t_name = f"0x{t:02x}"
                        v_str = v.decode(errors='ignore')[:30] if t == 0x68 or t == 0x67 else v.hex()
                        print(f"  Offset {sub_off:06x} | Tag {t_name} | Len {l} | Val: {v_str}")
                        sub_off += 8 + l
                    return

        offset = val_end

if __name__ == "__main__":
    hex_audit()
