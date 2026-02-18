
import os
import struct
import re

fp = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.3Q_sim14.data"

if not os.path.exists(fp):
    print(f"File not found: {fp}")
    exit()

with open(fp, "rb") as f:
    d = f.read()

print(f"File size: {len(d)} bytes")

# Find first occurrence of "Filled" or "Fill"
keywords = [b"Filled", b"Trade simulation fill", b"Fill"]
start_idx = -1
for k in keywords:
    m = re.search(k, d, re.IGNORECASE)
    if m:
        start_idx = m.start()
        print(f"Found keyword '{k.decode()}' at offset {start_idx}")
        break

if start_idx == -1:
    print("No keywords found.")
    exit()

# Look at the 200 bytes BEFORE and 200 bytes AFTER the keyword
s = max(0, start_idx - 200)
e = min(len(d), start_idx + 300)
chunk = d[s:e]

print(f"\n--- HEX DUMP around offset {start_idx} ---")
# Print hex in rows of 16
for i in range(0, len(chunk), 16):
    row_data = chunk[i:i+16]
    hex_str = " ".join(f"{b:02X}" for b in row_data)
    ascii_str = "".join((chr(b) if 32 <= b < 127 else ".") for b in row_data)
    print(f"{s+i:08X}  {hex_str:<48}  {ascii_str}")

print("\n--- Split by NULL Analysis ---")
context_chunk = d[max(0, start_idx - 1000) : min(len(d), start_idx + 1000)]
parts = context_chunk.split(b'\x00')
for p in parts:
    if len(p) > 2:
        try:
            print(f"  [{len(p)}] {p.decode(errors='ignore')}")
        except:
            print(f"  [{len(p)}] <binary>")

