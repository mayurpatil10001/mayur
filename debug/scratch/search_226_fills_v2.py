import os

def search_fills():
    target_file = r"C:\SierraChart\SC results WF\ALLTradeActivityLogExport_vsim16 11052025-12192025.txt"
    with open(target_file, "r") as f:
        count = 0
        for line in f:
            if "2025-12-18" in line and "02:26" in line:
                print(line.strip())
                count += 1
            if count > 100:
                break
    print(f"Total lines found: {count}")

if __name__ == "__main__":
    search_fills()
