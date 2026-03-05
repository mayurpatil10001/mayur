import re, os

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
search_str = b"2025-12-18"

if not os.path.exists(path):
    print("File not found")
else:
    with open(path, 'rb') as f:
        d = f.read()
    
    indices = [m.start() for m in re.finditer(search_str, d)]
    print(f"Found {len(indices)} occurrences of {search_str.decode()}")
    
    for idx in indices[:10]:
        # Print 20 bytes before and 80 bytes after
        start = max(0, idx - 40)
        end = min(len(d), idx + 100)
        chunk = d[start:end]
        print(f"Offset {idx}: {chunk.hex()} | {chunk.decode(errors='ignore')}")
