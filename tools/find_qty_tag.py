
import struct
import os

def find_tag_value_3():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024)
        
    offset = 0
    file_len = len(d)
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        v_start = offset + 8
        v_end = v_start + length
        
        if tag == 0x68: # Msg
            s = d[v_start:v_end].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                print(f"\n--- FILL MSG AT {offset} ---")
                # Search nearby tags for value 3
                # Scan backwards 200 bytes and forwards 200 bytes
                scan_start = max(0, offset - 500)
                scan_end = min(file_len, offset + 500)
                
                off = scan_start
                while off < scan_end - 8:
                    t, l = struct.unpack('<II', d[off:off+8])
                    vs = off + 8
                    ve = vs + l
                    if ve > file_len: break
                    
                    if l == 4:
                         val = struct.unpack('<i', d[vs:ve])[0]
                         if val == 3:
                             print(f"  Tag {t} at {off} has value {val}")
                    elif l == 8:
                        try:
                            val_f = struct.unpack('<d', d[vs:ve])[0]
                            if abs(val_f - 3.0) < 0.001:
                                print(f"  Tag {t} (Double) at {off} has value {val_f}")
                        except: pass
                    off = ve
                # Stop after first few matches
                break
        
        offset = v_end

if __name__ == "__main__":
    find_tag_value_3()
