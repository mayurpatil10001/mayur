import os
import glob
import struct
import re

def scan_vsim16_notes():
    # Adjusted paths for Windows
    data_dir = r"c:\SierraChart\SC results WF"
    files = glob.glob(os.path.join(data_dir, "*V_SIM16*.data")) + glob.glob(os.path.join(data_dir, "*V_SIM16*.DATA"))
    files = sorted(list(set(files)))

    total_fills = 0
    no_note_fills = 0
    patterns_found = {}

    for fp in files:
        fn = os.path.basename(fp)
        # print(f"Scanning {fn}...")
        try:
            with open(fp, "rb") as bf:
                d = bf.read()
            
            file_len = len(d)
            offset = 0
            
            while offset < file_len - 8:
                tag, length = struct.unpack('<II', d[offset : offset+8])
                val_start = offset + 8
                val_end = val_start + length
                if val_end > file_len: break
                
                if tag == 0x68: # 104: Message String
                    s = d[val_start:val_end].decode(errors='ignore').strip()
                    s_lower = s.lower()
                    
                    if ("trade simulation fill" in s_lower or "fill: " in s_lower) and "updated internal position" not in s_lower:
                        total_fills += 1
                        
                        # The "Note" is typically a string like "AT_..." or "Trading Evaluator"
                        # In the user screenshot, the note is AT_NQ_TM(D-R-2+last50)
                        # Let's see if we can find it in the message string
                        
                        note_match = re.search(r'\[([^\]]+)\]', s) # Often SC puts notes in brackets or at the end
                        # Actually let's just look for the typical pattern
                        if "AT_NQ_TM" not in s:
                            no_note_fills += 1
                            # print(f"No Note Fill found in {fn}: {s}")
                        
                        # Count patterns to see what else is there
                        match = re.search(r'(AT_[^\s:]+)', s)
                        if match:
                            p = match.group(1)
                            patterns_found[p] = patterns_found.get(p, 0) + 1
                        else:
                            patterns_found["NONE"] = patterns_found.get("NONE", 0) + 1
                            
                offset = val_end
        except Exception as e:
            print(f"Error reading {fn}: {e}")

    print("\n--- Summary for V_SIM16 ---")
    print(f"Total Fills Scanned: {total_fills}")
    print(f"Fills without 'AT_NQ_TM' pattern: {no_note_fills}")
    print("\nNote patterns distribution:")
    for p, c in patterns_found.items():
        print(f"  {p}: {c}")

if __name__ == "__main__":
    scan_vsim16_notes()
