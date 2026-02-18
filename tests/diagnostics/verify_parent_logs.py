
import os
import struct

def strings_and_floats(filename):
    print(f"\nScanning: {filename}")
    if not os.path.exists(filename):
        print("  [ERROR] File not found!")
        return

    with open(filename, "rb") as f:
        content = f.read()
    
    # 1. String Search (for CL, IPS, 5dupli)
    print("  --- Strings (Account/Symbol) ---")
    found_strings = set()
    current_str = ""
    for byte in content:
        if 32 <= byte <= 126:
            current_str += chr(byte)
        else:
            if len(current_str) >= 4:
                # Filter interesting strings
                if "CL" in current_str or "IPS" in current_str or "3Q" in current_str:
                    found_strings.add(current_str)
            current_str = ""
    
    # Print interesting strings (limit matches)
    for s in sorted(list(found_strings)):
        print(f"    Found: {s}")

    # 2. Float Search (for 60.53, 59.28)
    print("  --- Floats (Price) ---")
    targets = [60.53, 59.28, 59.25, 6847.5, 6850.0]
    found_floats = []
    
    for i in range(len(content) - 8):
        chunk = content[i:i+8]
        try:
            val = struct.unpack('<d', chunk)[0]
            for t in targets:
                if abs(val - t) < 0.0001:
                    found_floats.append(f"    Found {t} at offset {i}: {val}")
        except:
            pass
            
    if found_floats:
        for f in found_floats[:20]: print(f)
        if len(found_floats) > 20: print("    ... (more matches)")
    else:
        print("    No target floats found.")

def main():
    # 1. 3Q_sim14 - Jan 20
    f1 = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-20_UTC.3Q_sim14.data"
    strings_and_floats(f1)
    
    # 2. IPS_TM_5dupli - Dec 03 (Note the 'i' at end)
    f2 = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-03_UTC.IPS_TM_5dupli.data"
    strings_and_floats(f2)

if __name__ == "__main__":
    main()
