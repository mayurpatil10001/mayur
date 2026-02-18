
import struct
import re
import os

def check_quantity_patterns():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
         # Try another one
         file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024)
        
    offset = 0
    file_len = len(d)
    
    count_matches = 0
    while offset < file_len - 8 and count_matches < 30:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore')
            s_lower = s.lower()
            
            # Existing regex
            qm_old = re.search(r"(?:qty|quantity|size|fill qty|q:|vol)\s*:?\s*(\d+)", s_lower)
            
            # New proposed regex
            qm_new = re.search(r"(?:buy|sell|bought|sold|long|short)\s+(\d+)", s_lower)
            
            if qm_new or qm_old:
                print(f"MSG: {s.strip()}")
                print(f"  OLD Match: {qm_old.group(1) if qm_old else 'None'}")
                print(f"  NEW Match: {qm_new.group(1) if qm_new else 'None'}")
                count_matches += 1
        
        offset = val_end

if __name__ == "__main__":
    check_quantity_patterns()
