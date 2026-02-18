import struct
import os
import re

def analyze_double_counting(fp):
    with open(fp, 'rb') as f:
        d = f.read()
    
    print(f"Analyzing {os.path.basename(fp)} for potential duplicate fills...")
    offset = 0
    msgs = []
    
    # We'll use the same logic as the nitro parser but just print
    while offset < len(d) - 12:
        next_marker = d.find(b'\x00\x00\x00', offset + 1)
        if next_marker == -1: break
        offset = next_marker - 1
        tag = d[offset]
        length = struct.unpack('<I', d[offset+4 : offset+8])[0]
        
        if tag == 0x68: # Message
            try:
                s = d[offset+8 : offset+8+length].decode(errors='ignore').lower()
                if any(x in s for x in ["fill", "trade", "order", "bought", "sold"]):
                    pm = re.search(r"(?:last|price|fillprice|at)[:\s]*(\d+\.?\d*)", s)
                    if pm:
                        p_val = pm.group(1)
                        side = "N/A"
                        if any(x in s for x in ["buy", "bought", "long"]): side = "BUY"
                        elif any(x in s for x in ["sell", "sold", "short"]): side = "SELL"
                        
                        msgs.append({
                            "offset": offset,
                            "price": p_val,
                            "side": side,
                            "text": s[:100].strip()
                        })
            except: pass
        offset += 8 + length

    print(f"Found {len(msgs)} potential 'fills' according to current logic.")
    
    # Check for clusters (same price/side near each other)
    for i in range(len(msgs) - 1):
        m1 = msgs[i]
        m2 = msgs[i+1]
        if m1['price'] == m2['price'] and m1['side'] == m2['side'] and (m2['offset'] - m1['offset'] < 2000):
            print(f"\n--- POTENTIAL DUPLICATE ---")
            print(f"Msg 1 [{m1['offset']:04x}]: {m1['text']}")
            print(f"Msg 2 [{m2['offset']:04x}]: {m2['text']}")

if __name__ == "__main__":
    test_file = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.TS_4.data"
    analyze_double_counting(test_file)
