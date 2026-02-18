
import struct
import re
import os

def trace_tags():
    file_path = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    if not os.path.exists(file_path):
        file_path = r'D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    
    if not os.path.exists(file_path):
        print("File not found.")
        return

    with open(file_path, "rb") as bf:
        d = bf.read(5 * 1024 * 1024)
        
    offset = 0
    file_len = len(d)
    
    # We want to find a fill and then look at the tags AROUND it.
    found_fill_offset = -1
    
    while offset < file_len - 8:
        tag, length = struct.unpack('<II', d[offset : offset+8])
        val_start = offset + 8
        val_end = val_start + length
        
        if tag == 0x68:
            s = d[val_start:val_end].decode(errors='ignore')
            if "trade simulation fill" in s.lower():
                print(f"FOUND FILL AT OFFSET {offset}: {s.strip()}")
                found_fill_offset = offset
                # Look at the previous 1000 bytes and next 1000 bytes for other tags
                break
        
        offset = val_end

    if found_fill_offset != -1:
        print("\nInvestigating nearby tags (relative to fill string):")
        # Go back a bit to see if there's a Tag 107 (Quantity) or similar
        start_invest = max(0, found_fill_offset - 2000)
        end_invest = min(file_len, found_fill_offset + 2000)
        
        off = start_invest
        while off < end_invest - 8:
            t, l = struct.unpack('<II', d[off : off+8])
            v_start = off + 8
            v_end = v_start + l
            if v_end > file_len: break
            
            # Print all tags and their values if interesting
            if t == 0x68:
                msg = d[v_start:v_end].decode(errors='ignore').strip()
                print(f"Tag 104 (Msg) [{off}]: {msg[:100]}")
            elif t == 107: # Sometimes Quantity
                try:
                    q = struct.unpack('<i', d[v_start:v_start+4])[0]
                    print(f"Tag 107 (Qty?) [{off}]: {q}")
                except: pass
            elif t == 103:
                print(f"Tag 103 (Sym) [{off}]: {d[v_start:v_end].decode(errors='ignore')}")
            elif t == 102:
                 # Time
                 pass
            else:
                # If short, maybe it's a numeric value
                if l == 4:
                    val = struct.unpack('<i', d[v_start:v_start+4])[0]
                    if 1 <= val <= 100:
                        print(f"Tag {t} (Int4) [{off}]: {val}")
                        
            off = v_end

if __name__ == "__main__":
    trace_tags()
