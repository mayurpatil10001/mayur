
import struct
import os
from collections import Counter

def analyze_ips_offsets_v2():
    f_path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data"
    acc_str = b"IPS_TM_5dupli"
    
    # Load raw text trades to get prices
    prices_to_find = set()
    txt_path = r"C:\SierraChart\SC results WF\IPS_TM_5_dupli_03122025_TradesList.txt"
    with open(txt_path, 'r') as f:
        lines = f.readlines()
        for l in lines[1:]:
            parts = l.split('\t')
            if len(parts) > 17 and "2025-12-03" in parts[2]:
                try:
                    prices_to_find.add(round(float(parts[4]), 2)) # Entry
                    prices_to_find.add(round(float(parts[5]), 2)) # Exit
                except: continue
    
    print(f"Searching for {len(prices_to_find)} unique prices in windows after {acc_str}")
    
    with open(f_path, 'rb') as f:
        content = f.read()
        
    start = 0
    offsets_found = []
    while True:
        idx = content.find(acc_str, start)
        if idx == -1: break
        
        # Scan window after account string (e.g. 800 bytes)
        window_size = 800
        limit = min(len(content), idx + window_size)
        chunk = content[idx:limit]
        
        for i in range(len(chunk)-8):
            val = struct.unpack('<d', chunk[i:i+8])[0]
            val_rounded = round(val, 2)
            if val_rounded in prices_to_find:
                offsets_found.append(i)
        
        start = idx + 1
        
    counts = Counter(offsets_found)
    print("\nMost common offsets found in window:")
    # Filter out very low counts or show all
    for off, count in counts.most_common(20):
        print(f"  +{off}: {count} occurrences")

if __name__ == "__main__":
    analyze_ips_offsets_v2()
