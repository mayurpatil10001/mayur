
import os
import struct

def inspect_around_float(filename, target_float, context=150):
    print(f"\nScanning {filename} for {target_float}...")
    with open(filename, 'rb') as f:
        content = f.read()
        
    found_count = 0
    for i in range(len(content) - 8):
        chunk = content[i:i+8]
        try:
            val = struct.unpack('<d', chunk)[0]
            if abs(val - target_float) < 0.0001:
                found_count += 1
                start = max(0, i - context)
                end = min(len(content), i + context)
                snippet = content[start:end]
                
                print(f"\n[MATCH #{found_count}] Found {val} at offset {i}")
                # Print readable string in snippet
                readable = ""
                for b in snippet:
                    if 32 <= b <= 126: readable += chr(b)
                    else: readable += "."
                print(f"  Context String: {readable}")
                
                if found_count >= 5: break
        except: pass

def inspect_around_string(filename, target_str, context=150):
    print(f"\nScanning {filename} for string '{target_str}'...")
    with open(filename, 'rb') as f:
        content = f.read()
        
    # Simple byte search
    b_target = target_str.encode('utf-8')
    found_count = 0
    
    index = 0
    while True:
        index = content.find(b_target, index)
        if index == -1: break
        
        found_count += 1
        start = max(0, index - context)
        end = min(len(content), index + context)
        snippet = content[start:end]
        
        print(f"\n[MATCH #{found_count}] Found '{target_str}' at offset {index}")
        readable = ""
        for b in snippet:
            if 32 <= b <= 126: readable += chr(b)
            else: readable += "."
        print(f"  Context String: {readable}")
        
        index += 1 # Move forward
        if found_count >= 5: break

def main():
    # Redirect stdout to file manually or just write to file
    with open("raw_scan_results.txt", "w", encoding="utf-8") as out:
        import sys
        sys.stdout = out
        
        # 3Q - Search for 60.53
        f1 = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-20_UTC.3Q_sim14.data"
        inspect_around_float(f1, 60.53)
        
        # IPS - Search for CL strings and check context for Price?
        f2 = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data"
        inspect_around_string(f2, "CLF26")

if __name__ == "__main__":
    main()
