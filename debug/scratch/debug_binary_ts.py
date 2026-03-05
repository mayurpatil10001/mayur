import os
import struct

def debug_ts_tag():
    data_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
    if not os.path.exists(data_path): return

    with open(data_path, "rb") as bf:
        d = bf.read(100000) # just first chunk
    
    offset = 0
    found_66 = 0
    while offset < len(d) - 16 and found_66 < 5:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        if tag == 0x66:
            found_66 += 1
            val = d[offset+8:offset+8+length]
            print(f"Tag 0x66 | Length {length} | Hex: {val.hex()}")
            if length == 8:
                try: 
                    d_val = struct.unpack('<d', val)[0]
                    q_val = struct.unpack('<q', val)[0]
                    print(f"  As Double: {d_val}")
                    print(f"  As Long Long: {q_val}")
                except: pass
        offset += 8 + length

if __name__ == "__main__":
    debug_ts_tag()
