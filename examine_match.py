
import re
import struct
import os

path = r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs\TradeActivityLog_2024-09-30_UTC.IPS_TM_5dupli.data"
if not os.path.exists(path):
    print("File not found")
    exit()

with open(path, 'rb') as f:
    data = f.read(1000000) # Read 1MB

pattern = rb"Bid: ([\d\.]+)\s+Ask: ([\d\.]+)\s+Last: ([\d\.]+)"
for match in re.finditer(pattern, data):
    offset = match.start()
    print(f"\n--- MATCH AT OFFSET {offset} ---")
    print(f"Content: {match.group().decode()}")
    
    # Dump neighborhood
    start = max(0, offset - 64)
    end = min(len(data), offset + 64)
    segment = data[start:end]
    print(f"Hex: {segment.hex()}")
    
    # Try interpreting bytes before as timestamp
    # Does SC use 8-byte double for timestamp here?
    for j in range(offset - 16, offset):
        if j + 8 <= len(data):
            val_d = struct.unpack('<d', data[j:j+8])[0]
            if 43000 < val_d < 60000:
                 print(f"  Pos {j}: Double {val_d}")
        if j + 4 <= len(data):
             val_i = struct.unpack('<I', data[j:j+4])[0]
             if 1600000000 < val_i < 1800000000:
                 print(f"  Pos {j}: Int {val_i}")
    
    # Look for Symbol (e.g. CL, ES)
    # Usually it appears before the "Trading Evaluator" msg
    nearby_str = re.findall(b'[A-Z0-9]{2,10}', data[max(0, offset-500):offset])
    print(f"  Nearby Symbols: {nearby_str}")
    
    break
