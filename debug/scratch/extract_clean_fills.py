import os
import re

log_path = 'import_debug.log'
out_path = '/tmp/vsim16_dec18_clean_fills.txt'

if not os.path.exists(log_path):
    print("Log not found")
else:
    with open(log_path, 'r') as f:
        # Read the file in reverse to find the LATEST audit run
        lines = f.readlines()
        
        audit_lines = []
        found_end = False
        # Search from end for the last "--- END AUDIT ---"
        for i in range(len(lines)-1, -1, -1):
            if "--- END AUDIT ---" in lines[i]:
                found_end = True
            if found_end:
                if "DEBUG: FILL:" in lines[i]:
                    # Extract timestamp, symbol, side, qty, price
                    m = re.search(r'FILL: ([\d\-T:]+\.?\d*) \| (\w+) \| (\w+) \| (\d+) \| ([\d\.]+)', lines[i])
                    if m:
                        ts, sym, side, qty, price = m.groups()
                        audit_lines.append(f"{ts} | {sym} | {side} | {qty} | {price}")
                if "--- RAW FILLS AUDIT FOR V_SIM16 ON 2025-12-18 ---" in lines[i]:
                    break
        
        # Reverse because we collected from end
        audit_lines.reverse()
        
        with open(out_path, 'w') as out:
            out.write("TIMESTAMP | SYMBOL | SIDE | QTY | PRICE\n")
            out.write("-" * 50 + "\n")
            for line in audit_lines:
                out.write(line + "\n")
        
        print(f"Clean fills saved to {out_path}")
        print(f"Extracted {len(audit_lines)} fills.")
