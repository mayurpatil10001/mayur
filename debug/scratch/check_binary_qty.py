import os
import sys
import struct

# Add the project root to sys.path
project_root = r"c:\SierraChart\SC results WF"
sys.path.append(project_root)

target_fp = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"

def dump_vsim_qty(fp):
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
            # Window 09:46:00 to 09:47:00
            if 3975212760000000 <= micros <= 3975212780000000:
                peek = val_end
                ms_text = ""
                q_val = -1
                oid = ""
                while peek < file_len - 8:
                    t, l = struct.unpack('<II', d[peek:peek+8])
                    if t == 102: break
                    v = d[peek+8:peek+8+l]
                    if t == 104: ms_text = v.decode(errors='ignore').strip()
                    if t == 108: # Qty
                        if l == 8: q_val = struct.unpack('<d', v[:8])[0]
                        elif l == 4: q_val = struct.unpack('<i', v[:4])[0]
                    if t == 106 or t == 100 or t == 124: oid = v.decode(errors='ignore').strip()
                    peek += 8 + l
                
                if "Trade simulation fill" in ms_text:
                    print(f"TS: {micros} | OID: {oid} | QtyTag: {q_val} | Msg: {ms_text[:60]}")
        offset = val_end

dump_vsim_qty(target_fp)
