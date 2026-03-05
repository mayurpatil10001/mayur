import re, os

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
search_str = b"00:01" # Target the minute of the first processed SHORT entry

if not os.path.exists(path):
    print("File not found")
else:
    with open(path, 'rb') as f:
        d = f.read()
    
    indices = [m.start() for m in re.finditer(search_str, d)]
    print(f"Found {len(indices)} occurrences of {search_str.decode()}")
    
    for idx in indices:
        # Print 100 bytes before and 200 bytes after
        start = max(0, idx - 100)
        end = min(len(d), idx + 200)
        chunk = d[start:end]
        print(f"--- Offset {idx} ---")
        try:
            print(chunk.decode(errors='ignore'))
        except:
            print(f"HEX: {chunk.hex()}")
