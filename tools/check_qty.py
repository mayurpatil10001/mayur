import re
import os

def check_quantity(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Try to find common patterns for quantity
    patterns = [
        rb"Market \d+", rb"Limit \d+", rb"Quantity:? \d+", rb"Qty:? \d+", rb"Size:? \d+",
        rb"[\d\.]+ \d+ Filled"
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, data):
            print(f"Match: {match.group(0).decode(errors='ignore')} at {match.start()}")
            # Show context
            start = max(0, match.start() - 50)
            end = min(len(data), match.end() + 100)
            print(f"Context: {data[start:end].decode(errors='ignore')}")

if __name__ == "__main__":
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_19550-12-05_UTC.ES-TM_3.data"
    if os.path.exists(path):
        check_quantity(path)
