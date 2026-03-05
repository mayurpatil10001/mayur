import os
import sys
import struct
import datetime

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

from trading_platform.services.binary_log_parser import _parse_tag66_timestamp

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

# Exact micros for our target cluster (09:46:08, 09:46:11, 09:46:12)
# 2025-12-18 09:46:08.315 is approx 3975212768315000
# 2025-12-18 09:46:11.649 is approx 3975212771649296
# 2025-12-18 09:46:12.005 is approx 3975212772005811

def dump_range(fp, t_min, t_max):
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
            if t_min <= micros <= t_max:
                dt = _parse_tag66_timestamp(d[val_start:val_end])
                print(f"\n--- RECORD @ {offset} (TS: {micros} / {dt}) ---")
                
                peek = val_end
                while peek < file_len - 8:
                    t, l = struct.unpack('<II', d[peek:peek+8])
                    if t == 102: break
                    v = d[peek+8:peek+8+l]
                    t_name = {104: "Msg", 100: "OID", 124: "SvcOID", 130: "Note", 108: "Qty", 103: "Sym"}.get(t, f"Tag {t}")
                    try:
                        v_str = v.decode(errors='ignore').strip()
                        print(f"  {t_name:10s} | {v_str}")
                    except:
                         print(f"  {t_name:10s} | Binary {l} bytes")
                    peek += 8 + l
        offset = val_end

# Narrow window around 09:46:08 - 09:46:12
dump_range(target_fp, 3975212760000000, 3975212780000000)
