
import struct
import datetime
import os

def probe_all_numbers(filename, price_offset):
    with open(filename, 'rb') as f:
        content = f.read()

    print(f"Scanning ALL numbers near {price_offset}...")
    start = max(0, price_offset - 100)
    end = min(len(content), price_offset + 100)
    chunk = content[start:end]
    
    # Doubles
    print("--- Doubles ---")
    for i in range(len(chunk) - 8):
        sub = chunk[i:i+8]
        try:
            val = struct.unpack('<d', sub)[0]
            if 1.0 < abs(val) < 1000000.0: # Filter mostly zeros or huge numbers
                 print(f"  Double at relative {start + i - price_offset}: {val}")
        except: pass

    # Int64
    print("--- Int64 ---")
    for i in range(len(chunk) - 8):
        sub = chunk[i:i+8]
        try:
            val = struct.unpack('<q', sub)[0]
            if 1000000 < abs(val): # Filter small ints
                 print(f"  Int64 at relative {start + i - price_offset}: {val}")
        except: pass

def main():
    f = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-01-20_UTC.3Q_sim14.data"
    probe_all_numbers(f, 20287)

if __name__ == "__main__":
    main()
