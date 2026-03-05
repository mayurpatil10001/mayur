import os
import sys
import struct

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_tag66_timestamp

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

def deep_dump_cluster(fp):
    with open(fp, "rb") as f:
        d = f.read()
    
    offset = 0
    file_len = len(d)
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 102:
            micros = struct.unpack('<q', d[val_start:val_start+8])[0]
            # Window 09:46:11 to 09:46:13
            if 3975212771000000 <= micros <= 3975212773000000:
                print(f"\nRECORD @ {offset} (TS: {micros})")
                peek = val_end
                while peek < file_len - 8:
                    t, l = struct.unpack('<II', d[peek:peek+8])
                    if t == 102: break
                    v = d[peek+8:peek+8+l]
                    try:
                        v_str = v.decode(errors='ignore').strip()
                        print(f"  Tag {t:3d} | {v_str}")
                    except:
                        pass
                    peek += 8 + l
        offset = val_end

deep_dump_cluster(target_fp)
