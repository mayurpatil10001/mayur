import os

def probe_reset_string(filepath, target_string):
    print(f"Probing file: {filepath}")
    
    if not os.path.exists(filepath):
        print("File not found.")
        return

    b_target = target_string.encode('ascii') # Assume ASCII/UTF-8
    
    with open(filepath, 'rb') as f:
        content = f.read()
        
    count = 0
    start = 0
    while True:
        idx = content.find(b_target, start)
        if idx == -1: break
        
        count += 1
        # Show context around the string
        context_start = max(0, idx - 10)
        context_end = min(len(content), idx + len(b_target) + 50)
        
        # Try to decode or show hex
        raw_snippet = content[context_start:context_end]
        print(f"\nMatch #{count} at offset {idx}")
        print(f"  Raw context (Hex): {raw_snippet.hex()}")
        try:
            print(f"  Decoded context: {raw_snippet.decode('utf-8', errors='replace')}")
        except: pass
        
        start = idx + 1
        if count >= 10: 
            print("\n... (Stopped after 10 matches)")
            break

    print(f"\nTotal matches found: {count}")

if __name__ == "__main__":
    # IPS Dec 03
    probe_reset_string(
        r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data", 
        "Updated Service Position"
    )
