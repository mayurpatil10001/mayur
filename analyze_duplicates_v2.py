import struct
import os
import re

def analyze_double_counting(fp):
    with open(fp, 'rb') as f:
        d = f.read()
    
    print(f"Analyzing {os.path.basename(fp)}...")
    offset = 0
    msgs = []
    
    while offset < len(d) - 12:
        next_marker = d.find(b'\x00\x00\x00', offset + 1)
        if next_marker == -1: break
        offset = next_marker - 1
        tag = d[offset]
        length = struct.unpack('<I', d[offset+4 : offset+8])[0]
        
        if tag == 0x68:
            try:
                s = d[offset+8 : offset+8+length].decode(errors='ignore').lower()
                if any(x in s for x in ["fill", "trade", "order", "bought", "sold"]):
                    pm = re.search(r"(?:last|price|fillprice|at)[:\s]*(\d+\.?\d*)", s)
                    if pm:
                        p_val = pm.group(1)
                        msgs.append({"offset": offset, "price": p_val, "text": s})
            except: pass
        offset += 8 + length

    # Look for the cluster from the last output
    # The last output showed Msg 2 [2a760e]
    # Let's find messages around that area.
    print("\n--- Snippet near 0x2a7600 ---")
    relevant = [m for m in msgs if 0x2a7000 < m['offset'] < 0x2a8000]
    for m in relevant:
        print(f"[{m['offset']:06x}]: {m['text'][:150]}...")

if __name__ == "__main__":
    test_file = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.TS_4.data"
    analyze_double_counting(test_file)
