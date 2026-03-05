import os
import re

def search_fills():
    target_file = r"C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt"
    if not os.path.exists(target_file):
        print(f"File not found: {target_file}")
        return

    print("Searching for fills around 2025-12-18 02:20 - 02:30 NY...")
    # The file has local time (NY).
    with open(target_file, "r") as f:
        headers = f.readline()
        count = 0
        for line in f:
            if "2025-12-18 02:2" in line:
                print(line.strip())
                count += 1
            if count > 50:
                break

if __name__ == "__main__":
    search_fills()
