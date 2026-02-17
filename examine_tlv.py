
import struct
import os

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.3Q_sim14.data"

with open(fp, "rb") as f:
    d = f.read()

offset = 0
found_count = 0

print(f"Scanning {len(d)} bytes for Tag 104 (Message Strings)...")

while offset < len(d) - 8:
    # Look for Tag 104 (0x68) in Little Endian INT32
    # 68 00 00 00
    if d[offset] == 0x68 and d[offset+1] == 0x00 and d[offset+2] == 0x00 and d[offset+3] == 0x00:
        # Found Tag 104
        try:
            # Read Length (next 4 bytes)
            length = struct.unpack('<I', d[offset+4:offset+8])[0]
            
            # Read String
            if length < 5000: # Sanity check
                s_bytes = d[offset+8 : offset+8+length]
                # Decode (usually utf-8 or ascii)
                s = s_bytes.decode(errors='ignore')
                
                # Check for "Filled"
                if "Fill" in s:
                    print(f"OFFSET {offset}: LEN={length} => {s}")
                    found_count += 1
                
                # We can skip ahead by length (Wait, alignment might be different)
                # Let's just create a list of ALL valid strings to prove concept
        except Exception as e:
            pass
            
    offset += 1 # Brute force scan byte-by-byte to find the pattern
    
    if found_count > 20: break

print("Scan complete.")
