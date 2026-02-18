import re
import os
import struct

def _get_base_symbol_standalone(raw: str) -> str:
    s = raw.upper()
    match = re.search(r'([A-Z]+)', s)
    if not match: return s
    base = match.group(1)
    # Simple map for testing
    m = {'CLN': 'CL', 'CLH': 'CL', 'CLQ': 'CL', 'CLU': 'CL', 'CLV': 'CL', 'CLZ': 'CL'}
    if base in m: return m[base]
    if base == 'CL': return 'CL'
    return base

def debug_file(fp, target_sym="CL"):
    with open(fp, 'rb') as f:
        d = f.read()
    
    fn = os.path.basename(fp).upper()
    sh = "Unknown"
    filename_symbol_inferred = False
    
    # Filename inference logic (simplified)
    if "CL" in fn:
        sh = "CL"
        filename_symbol_inferred = True
        print(f"DEBUG: Inferred 'CL' from filename: {fn} (sh={sh})")

    offset = 0
    msgs = []
    
    while offset < len(d) - 12:
        next_marker = d.find(b'\x00\x00\x00', offset + 1)
        if next_marker == -1: break
        offset = next_marker - 1
        tag = d[offset]
        length = struct.unpack('<I', d[offset+4 : offset+8])[0]
        
        if tag == 0x68: # Message
            s = d[offset+8 : offset+8+length].decode(errors='ignore')
            s_upper = s.upper()

            if "FILL" in s_upper or "TRADE" in s_upper:
                asym = "Unknown"
                tm = re.search(r'\b([A-Z]{1,8}[FGHJKMNQUVXZ]\d{1,2})\b', s_upper)
                
                if tm:
                    asym = tm.group(1)
                    print(f"DEBUG: Found specific symbol in message: {asym}")
                elif sh != "Unknown" and filename_symbol_inferred:
                    asym = sh
                    print(f"DEBUG: Fallback to sh: {asym}")
                elif target_sym and "CL" in s_upper: # simplified check
                    asym = "CL"
                    print(f"DEBUG: Fallback to target CL")

                if target_sym:
                    base_check = _get_base_symbol_standalone(asym)
                    print(f"DEBUG: Checking base({asym}) -> {base_check} == {target_sym}?")
                    if base_check != target_sym:
                        print("DEBUG: SKIP (Mismatch)")
                        offset += 8 + length
                        continue
                    else:
                        print("DEBUG: MATCH!")

        elif tag == 0x67: # Symbol Tag
            tsym = d[offset+8 : offset+8+length].decode(errors='ignore').strip('\x00').strip()
            print(f"DEBUG: TAG 0x67 Found: {tsym}")
            if tsym:
                sh = tsym # My change: sh is now Specific
                # sh = _get_base_symbol_standalone(tsym) # Old logic
                filename_symbol_inferred = True
                print(f"DEBUG: Updated sh to {sh}")

        offset += 8 + length

if __name__ == "__main__":
    test_file = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.TS_4.data"
    print(f"Checking {test_file} ...")
    debug_file(test_file)
