
import struct
import os

def print_all_nearby_tags():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    with open(file_path, "rb") as bf:
        d = bf.read(10 * 1024 * 1024)
        
    offset = 0
    while offset < len(d) - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        v_start = offset + 8
        v_end = v_start + length
        
        if tag == 0x68: # Msg
            s = d[v_start:v_end].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                print(f"\n--- FILL MSG AT {offset} ---")
                scan_start = max(0, offset - 100)
                scan_end = min(len(d), offset + 500)
                
                off = scan_start
                while off < scan_end - 8:
                    t, l = struct.unpack('<II', d[off:off+8])
                    vs = off + 8
                    ve = vs + l
                    if ve > len(d): break
                    
                    if l == 4:
                         val_i = struct.unpack('<i', d[vs:ve])[0]
                         val_u = struct.unpack('<I', d[vs:ve])[0]
                         val_f = struct.unpack('<f', d[vs:ve])[0]
                         print(f"  Tag {t:3} [off={off:5}, len={l}]: Int={val_i:10} | Flt={val_f:10.2f}")
                    elif l == 8:
                        val_q = struct.unpack('<q', d[vs:ve])[0]
                        val_d = struct.unpack('<d', d[vs:ve])[0]
                        print(f"  Tag {t:3} [off={off:5}, len={l}]: Qry={val_q:10} | Dbl={val_d:10.2f}")
                    elif l < 50:
                        print(f"  Tag {t:3} [off={off:5}, len={l}]: Hex={d[vs:ve].hex()}")
                    off = ve
                break
        offset = v_end

if __name__ == "__main__":
    print_all_nearby_tags()
