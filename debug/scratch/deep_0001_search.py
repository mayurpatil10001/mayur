import re, os

path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2025-12-18_UTC.V_sim16.data"
# Search for the minute of the first SHORT entry in UTC
search_str = b"00:01" 

if not os.path.exists(path):
    print("File not found")
else:
    with open(path, 'rb') as f:
        d = f.read()
    
    indices = [m.start() for m in re.finditer(search_str, d)]
    print(f"Found {len(indices)} occurrences of {search_str.decode()}")
    
    for idx in indices:
        # Print a large chunk around the match
        start = max(0, idx - 1000)
        end = min(len(d), idx + 2000)
        chunk = d[start:end]
        print(f"--- Offset {idx} ---")
        try:
            # Clean non-printable chars for clearer view
            text = chunk.decode(errors='ignore')
            # Look for 'fill' or 'Evaluator' or 'position'
            if "fill" in text.lower() or "evaluator" in text.lower() or "position" in text.lower():
                print(text)
        except:
            print(f"HEX: {chunk.hex()}")
