import os
import glob
import struct
import re

def scan_vsim16_notes():
    data_dir = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    # Case insensitive search for V_sim16
    pattern = os.path.join(data_dir, "*v_sim16*.data")
    files = glob.glob(pattern)
    files += glob.glob(os.path.join(data_dir, "*v_sim16*.DATA"))
    files = sorted(list(set(files)))

    total_fills = 0
    no_note_fills = 0
    pattern_to_match = "AT_NQ_TM"
    
    no_note_examples = []

    for fp in files:
        fn = os.path.basename(fp)
        try:
            with open(fp, "rb") as bf:
                d = bf.read()
            
            file_len = len(d)
            offset = 0
            current_time = "Unknown"
            
            while offset < file_len - 8:
                tag, length = struct.unpack('<II', d[offset : offset+8])
                val_start = offset + 8
                val_end = val_start + length
                if val_end > file_len: break
                
                # Tag 0x66 (102) is Time
                if tag == 0x66:
                    # Logic to parse timestamp would be here, but we can just use the most recent one
                    pass

                elif tag == 0x68: # 104: Message String
                    s = d[val_start:val_end].decode(errors='ignore').strip()
                    s_lower = s.lower()
                    
                    if ("trade simulation fill" in s_lower or "fill: " in s_lower) and "updated internal position" not in s_lower:
                        total_fills += 1
                        
                        if pattern_to_match not in s:
                            no_note_fills += 1
                            if len(no_note_examples) < 10:
                                no_note_examples.append(f"{fn} | {s}")
                            
                offset = val_end
        except Exception as e:
            # print(f"Error reading {fn}: {e}")
            pass

    print("\n--- Summary for V_SIM16 (Binary Scan on D: drive) ---")
    print(f"Total Files Scanned: {len(files)}")
    print(f"Total Fills Found: {total_fills}")
    print(f"Fills MISSING '{pattern_to_match}' in Message String: {no_note_fills}")
    print("\nRecent 'No Note' Example Fills:")
    for ex in no_note_examples:
        print(f"  - {ex}")

if __name__ == "__main__":
    scan_vsim16_notes()
