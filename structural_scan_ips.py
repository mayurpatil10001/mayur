
import struct
import os

def scan_ips_v2():
    f = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data"
    target = b"IPS_TM_5dupli"
    # Target prices from text file
    targets = [58.63, 58.89, 59.05, 59.31, 59.32]
    
    with open(f, 'rb') as f:
        content = f.read()
    
    print(f"File size: {len(content)}")
    print(f"Searching for {target}...")
    
    start = 0
    found_any = False
    match_count = 0
    while True:
        idx = content.find(target, start)
        if idx == -1: break
        
        match_count += 1
        if match_count % 1000 == 0:
            print(f"Processed {match_count} occurrences...")

        # Scan +/- 500 bytes
        s = max(0, idx - 500)
        e = min(len(content), idx + 500)
        chunk = content[s:e]
        for i in range(len(chunk)-8):
            val = struct.unpack('<d', chunk[i:i+8])[0]
            for t in targets:
                if abs(val - t) < 0.0001:
                    print(f"Found Price {val} at relative {s + i - idx}")
                    found_any = True
                    break
        
        if found_any and match_count > 10: # Stop after finding first matches to get offset
             # Actually let's find a few to be sure it's consistent
             if match_count > 50: break
             
        start = idx + 1

    if not found_any:
        print("No price targets found near account record.")

if __name__ == "__main__":
    scan_ips_v2()
