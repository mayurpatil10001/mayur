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

def check_all_notes():
    log_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    target_acc = "V_sim16"
    
    unique_notes = set()
    
    # Check 10 files from different months
    files = [f for f in os.listdir(log_dir) if target_acc.upper() in f.upper()]
    files.sort()
    
    sample_files = files[::max(1, len(files)//10)]
    
    for fn in sample_files:
        path = os.path.join(log_dir, fn)
        with open(path, "rb") as bf: d = bf.read()
        
        offset = 0
        while offset < len(d) - 8:
            tag, length = struct.unpack('<II', d[offset : offset+8])
            val_start, val_end = offset + 8, offset + 8 + length
            if val_end > len(d): break
            
            if tag == 0x82:
                note = d[val_start:val_end].decode(errors='ignore').strip()
                if note:
                    # Clean the note (remove dynamic parts like (D-R-2...))
                    # AT_NQ_TM(D-R-2+last50) -> AT_NQ_TM
                    prefix = re.split(r'\(', note)[0]
                    unique_notes.add(prefix)
            offset = val_end
            
    print(f"Unique Note Prefixes for {target_acc}:")
    for n in sorted(list(unique_notes)):
        print(f" - {n}")

if __name__ == "__main__":
    check_all_notes()
