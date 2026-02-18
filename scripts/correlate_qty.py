
import struct
import os
import re

def correlate():
    data_file = r'D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-17_UTC.3Q_sim14.data'
    txt_file = r'C:\SierraChart\SC results WF\TradeActivityLogExport_3Q_sim14_2026-02-17.txt'
    
    if not os.path.exists(data_file) or not os.path.exists(txt_file):
        print("Missing one of the files.")
        return

    # Get a few fills from TXT
    fills_txt = []
    with open(txt_file, 'r') as f:
        header = f.readline().split('\t')
        q_idx = header.index('Quantity')
        fq_idx = header.index('FilledQuantity')
        t_idx = header.index('DateTime')
        s_idx = header.index('Symbol')
        for line in f:
            parts = line.split('\t')
            if len(parts) > q_idx and parts[0] == 'Fills':
                # Use FilledQuantity if Quantity is 0 or empty
                qty = parts[fq_idx].strip() if parts[fq_idx].strip() else parts[q_idx].strip()
                fills_txt.append({
                    'time': parts[t_idx],
                    'qty': qty,
                    'sym': parts[s_idx]
                })

    print(f"Found {len(fills_txt)} fills in TXT.")
    
    # Read binary
    with open(data_file, 'rb') as bf:
        d = bf.read()
        
    # Search for a specific time or symbol to find the binary record
    target_fill = fills_txt[0]
    print(f"Targeting fill: {target_fill}")
    
    # The time in TXT is "2026-01-01 21:58:35.732149" (wait, the file name says 2026-02-17)
    # Ah, the TXT might be cumulative.
    
    # Let's find a fill FROM TODAY in the TXT
    fills_today = [f for f in fills_txt if "2026-02-17" in f['time']]
    print(f"Found {len(fills_today)} fills from today in TXT.")
    
    if not fills_today: 
        # Maybe the dates are different. Let's just use the first 50.
        fills_today = fills_txt[:50]

    for target in fills_today[:5]:
        print(f"\nLooking for fill in binary: {target}")
        # Search for symbol in binary strings
        sym_bytes = target['sym'].encode()
        
        # Scan binary for tags near the symbol
        offset = 0
        while offset < len(d) - 8:
            tag, length = struct.unpack('<II', d[offset:offset+8])
            v_start = offset + 8
            v_end = v_start + length
            
            if tag == 0x68: # Msg
                s = d[v_start:v_end].decode(errors='ignore')
                if "trade simulation fill" in s.lower() and target['sym'] in s:
                    print(f"MATCHING MSG AT {offset}: {s.strip()}")
                    # Look for the quantity near here
                    # Check tags in the 500 bytes before and after
                    search_start = max(0, offset - 1000)
                    search_end = min(len(d), offset + 1000)
                    
                    off = search_start
                    while off < search_end - 8:
                        t, l = struct.unpack('<II', d[off:off+8])
                        vs = off + 8
                        ve = vs + l
                        if ve > len(d): break
                        
                        # We are looking for the value in target['qty']
                        try:
                            if l == 4:
                                val_i = struct.unpack('<i', d[vs:ve])[0]
                                if str(val_i) == target['qty']:
                                    print(f"  POTENTIAL QTY TAG: {t} at offset {off} has value {val_i}")
                            elif l == 8:
                                val_f = struct.unpack('<d', d[vs:ve])[0]
                                if abs(val_f - float(target['qty'])) < 0.001:
                                    print(f"  POTENTIAL QTY TAG (Float): {t} at offset {off} has value {val_f}")
                        except: pass
                        off = ve
            offset = v_end

if __name__ == "__main__":
    correlate()
