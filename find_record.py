import re
import os

def find_exact_record(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # Try to find the price anywhere
    # NQ 24823.50
    # Search for the string "24823.50"
    patterns = [rb"24823.50", rb"24823.5", rb"TM_3"]
    
    for pattern in patterns:
        for match in re.finditer(pattern, data):
            print(f"Found {pattern} at {match.start()}")
            # Dump 400 bytes around it
            start = max(0, match.start() - 200)
            end = min(len(data), match.end() + 200)
            print(f"Context: {data[start:end]}")

if __name__ == "__main__":
    # Correct file based on symbol and account
    path = r"D:\SierraChart_Simulated_Feed\TradeActivityLogs\TradeActivityLog_2026-02-13_UTC.NQ-TM_3.data"
    # Actually, the user's path shows NQ in SierraChartInstance_4 but the trade list header says Sim Feed
    # Let's try to find it.
    dirs = [
        r"D:\SierraChart_Simulated_Feed\SierraChartInstance_4\TradeActivityLogs",
        r"D:\SierraChart_Simulated_Feed\TradeActivityLogs"
    ]
    for d in dirs:
        if os.path.exists(d):
            files = os.listdir(d)
            for f in files:
                if "NQ" in f and "TM_3" in f:
                    print(f"Checking {f} in {d}")
                    find_exact_record(os.path.join(d, f))
